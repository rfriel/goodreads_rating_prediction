
# coding: utf-8

# In[1]:

from scrape_GR_tools import *

# In[2]:

def userFromRecentReviews():
    urlRecent = 'https://www.goodreads.com/review/recent_reviews'
    soup = BeautifulSoup(requests.get(urlRecent,cookies=cookies()).content, 'lxml')
    uR = soup.select('.userReview')

    # change this to use random.choice
    randUser = uR[np.random.randint(len(uR)/2)*2] #odd-numbered elements contain no links
    href = randUser.find_next('a').get('href')
    try:
        uID = int(href[11:href.find('-')])
    except ValueError:
        return None
    return uID


def bookTitle(bookID):
    urlBook = 'https://www.goodreads.com/book/show/' + str(bookID)
    soup = BeautifulSoup(requests.get(urlBook,cookies=cookies()).content, 'lxml')

    title = soup.select('.bookTitle')[0].text.strip()

    try:
        nRatings = int(soup.find_all(itemprop="ratingCount")[0].get('title'))
    except IndexError:
        return None, None

    return title, nRatings

def userFromBook(bookID):
    urlBook = 'https://www.goodreads.com/book/show/' + str(bookID)
    soup = BeautifulSoup(requests.get(urlBook,cookies=cookies()).content, 'lxml')

    bookTitle = soup.select('.bookTitle')[0].text.strip()
    try:
        nRatings = int(soup.find_all(itemprop="ratingCount")[0].get('title'))
    except IndexError:
        return None, None

    if nRatings < 1:
        return None, None

    randRatingIndex = np.random.randint(nRatings)
    page = randRatingIndex/30 + 1

    urlBookPage = 'https://www.goodreads.com/book/delayable_book_show/'     + str(bookID) + '?page=' + str(page)

    soup = BeautifulSoup(requests.get(urlBookPage,cookies=cookies()).content, 'lxml')

    indexOnPage = randRatingIndex - 30*(page-1)

    users = soup.select('.user')
    href = users[indexOnPage].get('href')
    try:
        uID = int(href[11:href.find('-')])
    except ValueError:
        return None, None
    return uID, bookTitle


def populate_friends(ratingsCollection, friendsCollection, booksCollection, sleepTime):
    ratingsRecords = ratingsCollection.find()

    for record in ratingsRecords:
        userID = record['userID']
        if friendsCollection.find({'userID': {'$eq': userID}}).count() == 0:
            # don't have friends for this user, scrape them
            friendIDs = getFriends(sleepTime, userID)
            friendsToMongo(friendsCollection, userID, friendIDs)
        else:
            friendIDs = friendsCollection.find_one({'userID': {'$eq': userID}})['friends']
        friendCount = len(friendIDs)

        # count how many friends exist in the ratings db
        friendsExplored = []
        for friendID in friendIDs:
            if ratingsCollection.find({'userID': {'$eq': friendID}}).count() > 0:
                friendsExplored.append(friendID)
        exploredCount = len(friendsExplored)

        friendsCollection.update_one(
            {"userID": userID},
            {"$set":
            {"friendsExplored": friendsExplored}
            },
            upsert=True)

        print 'User %d has %d friends explored, or %f%% of their friends.' % (userID,
                                                                              exploredCount,
                                                                              100*float(exploredCount)/
                                                              max(1, friendCount))

# In[5]:

def computeFriendRatingFractions(ratingsCollection, friendsCollection, booksCollection, sleepTime, sampleRate=1, limit=-1):
    ratingsRecords = ratingsCollection.find(no_cursor_timeout=True)
    startTime = timeit.default_timer()
    sampleSize = 0
    allUserFractions = {}

    for record in ratingsRecords:
        userID = record['userID']
        ratingDict = record['ratings'] # keys are bookIDs
        userFractions = []
        for bookID in ratingDict.keys():
            randDraw = np.random.rand()
            if randDraw < sampleRate:
                try:
                    allRatingsForBook = booksCollection.find_one({'bookID': {'$eq': int(bookID)}})['ratings'] # dict, keys are userIDs
                except TypeError:
                    allRatingsForBook = []
                if len(allRatingsForBook) > 1:
                    allRatersForBook = set([int(uID) for uID in allRatingsForBook.keys()])
                    userFriendIDs = set(friendsCollection.find_one({'userID': {'$eq': userID}})['friends'])
                    friendRaters = allRatersForBook.intersection(userFriendIDs)
                    fractionOfRatersWhoAreFriends  = float(len(friendRaters)) / len(allRatersForBook)
                    userFractions.append(fractionOfRatersWhoAreFriends)
        allUserFractions[userID] = userFractions
        sampleSize += len(userFractions)
        if len(allUserFractions) % 10 == 1:
            print len(allUserFractions)
            endTime = timeit.default_timer()
            print 'Time: %f s' % (endTime - startTime)
            print '%d, or %f%%' % (sampleSize, 100*float(sampleSize)/limit)
            startTime = timeit.default_timer()
        if sampleSize > limit and limit > 0:
            break
        #if len(userFractions) > 0:
        #    print 'Mean fraction for user %d is %f' % (userID, float(sum(userFractions))/len(userFractions))
    ratingsRecords.close()
    return allUserFractions


def exploreFromRecent(ratingsCollection, friendsCollection, booksCollection, sleepTime, scrapeLimit=-1):
    usersScraped = 0
    ratingDict = {}
    testRatingDict = {}

    while usersScraped < scrapeLimit or scrapeLimit < 0:
        while testRatingDict == {}:
            if usersScraped == 0:
                testUserID = userFromRecentReviews()
            else:
                testUserID = None
                while testUserID == None:
                    try:
                        testBookID = choice(ratingDict.keys())
                    except IndexError:
                        pdb.set_trace()
                    testUserID, bookTitle = userFromBook(testBookID)
            if ratingsCollection.find({"userID": testUserID}).count() == 0:
                # don't have this user's ratings, scrape them
                if usersScraped > 0:
                    print 'Linking via book %d (%s).' % (testBookID, bookTitle)
                usersScraped += 1
                testRatingDict = getReviews(sleepTime, testUserID)
                ratingsToMongo(ratingsCollection, testUserID, testRatingDict)
                booksToMongo(booksCollection, testUserID, testRatingDict)
        # got a populated ratingDict, record it and the user
        ratingDict = testRatingDict
        userID = testUserID
        # reset testRatingDict to search for a new one
        testRatingDict = {}


def exploreFromRecentMultigraph(ratingsCollection, friendsCollection, booksCollection, sleepTime, scrapeLimit=-1):
    # this function is a mess of conditionals.  should clean up the flow later
    usersScraped = 0
    ratingDict = {}
    testRatingDict = {}

    while usersScraped < scrapeLimit or scrapeLimit < 0:
        successfulStep = False
        atLeastOneRating = True # we know the first user rated a book because we got them from the recent reviews page
        while not successfulStep:
            if usersScraped == 0:
                testUserID = userFromRecentReviews()
            else:
                ratingDegree = len(ratingDict)
                friendDegree = getFriends(sleepTime, userID, friendCountOnly=True) # record this in the db!!
                try:
                    #randDraw = np.random.randint(ratingDegree + friendDegree) + 1
                    #chooseRatingGraph = randDraw <= ratingDegree
                    randDraw = np.random.rand()
                    chooseRatingGraph = ((randDraw <= 0.5) and (ratingDegree != 0)) or (friendDegree == 0)
                    #chooseRatingGraph = (friendDegree == 0)
                    print '\nratingDegree %d, friendDegree %d, random draw %f, chooseRatingGraph: %d' % (ratingDegree, friendDegree, randDraw, int(chooseRatingGraph))
                except ValueError:
                    print 'Got ratingDegree %d, friendDegree %d, should not have stepped here.  Entering debugger...' % (ratingDegree, friendDegree)
                    pdb.set_trace()
                if chooseRatingGraph:
                    testUserID = None
                    while testUserID == None:
                        try:
                            testBookID = choice(ratingDict.keys())
                        except IndexError:
                            pdb.set_trace()
                        testUserID, bookTitle = userFromBook(testBookID)
                    atLeastOneRating = True # we got to this user via a rating of theirs so they have at least one
                    print 'Linking via book %d (%s).\n' % (testBookID, bookTitle)
                else:
                    if friendsCollection.find({"userID": userID}).count() == 0:
                        # don't have the pre-step user's friends, scrape them
                        friendIDs = getFriends(sleepTime, userID)
                        friendsToMongo(friendsCollection, userID, friendIDs)
                    else:
                        friendIDs = friendsCollection.find_one({"userID": userID})['friends']
                    testUserID = choice(friendIDs)
                    atLeastOneRating = False
                    print 'Linking via friendship with user %d.\n' % testUserID

            if ratingsCollection.find({"userID": testUserID}).count() == 0:
                # don't have this user's ratings, scrape them
                testRatingDict = getReviews(sleepTime, testUserID, atLeastOneRating)
                if testRatingDict is not None:
                    ratingsToMongo(ratingsCollection, testUserID, testRatingDict)
                    booksToMongo(booksCollection, testUserID, testRatingDict)
                    usersScraped += 1
                    successfulStep = True

        # successfully moved to new user testUserID, and scraped if necessary
        # now set things up for the next loop

        # this distinction is obsolete, should replace testRatingDict with
        # ratingDict everywhere
        ratingDict = testRatingDict
        userID = testUserID

def exploreFromBook(bookID, ratingsCollection, friendsCollection, booksCollection, sleepTime, scrapeLimit=-1, scrapeFriends=False):
    urlBook = 'https://www.goodreads.com/book/show/' + str(bookID)
    soup = BeautifulSoup(requests.get(urlBook,cookies=cookies()).content, 'lxml')

    bookTitle = soup.select('.bookTitle')[0].text.strip()
    try:
        nRatings = int(soup.find_all(itemprop="ratingCount")[0].get('title'))
    except IndexError:
        print 'Could not find number of ratings.'
        return None

    if nRatings < 1:
        print 'Found zero ratings.'
        return None

    nPages = 10#nRatings/50 + 1
    allUIDs = set()

    if booksCollection.find({'bookID': bookID, 'allUIDs': {'$exists': True}}).count() == 0:
        # don't have a list of all users who rated this book, scrape it
        sortStrings = ['default', 'oldest', 'newest']
        for sortIndex in range(2):
            for page in range(1, nPages+1):
                print 'Scraping book\'s raters (page %d of %d)...' % (page, nPages)
                urlBookPage = 'https://www.goodreads.com/book/delayable_book_show/' + str(bookID) + \
                    '?per_page=50&page=' + str(page) + '&sort=' + sortStrings[sortIndex]

                soup = BeautifulSoup(requests.get(urlBookPage,cookies=cookies()).content, 'lxml')

                users = soup.select('.user')
                hrefs = [users[index].get('href') for index in range(len(users))]
                uIDs = [int(href[11:href.find('-')]) for href in hrefs]
                print len(allUIDs)
                allUIDs.update(uIDs)
            booksCollection.update_one(
                {"bookID": bookID},
                {"$set": {"allUIDs": list(allUIDs)}},
                upsert=True)

    else:
        allUIDs.update(booksCollection.find_one({'bookID': bookID})['allUIDs'])

    unscrapableUIDs = set()

    for userID in allUIDs:
        if False:#ratingsCollection.find({"userID": userID}).count() == 0:
            # don't have this user's ratings, scrape them
            ratingDict = getReviews(sleepTime, userID)
            if ratingDict is not None:
                ratingsToMongo(ratingsCollection, userID, ratingDict)
                booksToMongo(booksCollection, userID, ratingDict)
            else:
                unscrapableUIDs.add(userID)
            if (ratingsCollection.find().count() % 10) == 0:
                print "%d users scraped of (at most) %d." % (ratingsCollection.find().count(), len(allUIDs))

        if friendsCollection.find({"userID": userID}).count() == 0:
            # don't have this user's friends, scrape them
            friendIDs = getFriends(sleepTime, userID)
            if friendIDs is not None:
                friendsToMongo(friendsCollection, userID, friendIDs)
            if (friendsCollection.find().count() % 10) == 0:
                print "%d users scraped of (at most) %d." % (friendsCollection.find().count(), len(allUIDs))

    allUIDs -= unscrapableUIDs

    booksCollection.update_one(
        {"bookID": bookID},
        {"$set": {"allUIDs": list(allUIDs)}},
        upsert=True)




# In[6]:

if __name__ == '__main__':
    # setting up mongodb

    mongoClientName = "mongodb://" + sys.argv[1]
    # pass the location of your mongo client as a command line argument
    # in my project I used one of my Amazon EC2 instances and its associated storage as a central location for MongoDB

    client = MongoClient(mongoClientName)

    with open('focalbook.txt') as f:
        focalBookID = int(f.next())
        focalBookCollectionTag = f.next().rstrip()

    #db = client['goodreads_explore_from_book_' + focalBookCollectionTag]
    db = client['goodreads_full']

    friends = db['friends']
    ratings = db['reviews']
    books = db['books']

    # DEBUG/TESTING ONLY -- deletes everything we have !!
    # reset_colls(friends, ratings, books)

    #exploreFromRecentMultigraph(ratings, friends, books, 0.05)

    #adj_dict = {int(k): v for k, v in db['adj_dict'].find_one()['adj_dict'].items()}
    #completeAdjDict(ratings, books, adj_dict, 0.05)

    populateComms(db, 0.05, db['comms'].find_one()['comms'])

    #exploreFromBook(focalBookID, ratings, friends, books, 0.05)
