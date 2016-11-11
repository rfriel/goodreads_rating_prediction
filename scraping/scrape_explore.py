
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


# In[3]:

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
                                                                                  friendCount)

# In[5]:

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
        while not successfulStep:
            if usersScraped == 0:
                testUserID = userFromRecentReviews()
            else:
                ratingDegree = len(ratingDict)
                friendDegree = getFriends(sleepTime, userID, friendCountOnly=True)
                try:
                    randDraw = np.random.randint(ratingDegree + friendDegree) + 1
                    chooseRatingGraph = randDraw <= ratingDegree
                    print '\nratingDegree %d, friendDegree %d, random draw %d, chooseRatingGraph: %d' % (ratingDegree, friendDegree, randDraw, int(chooseRatingGraph))
                except ValueError:
                    print 'Got ratingDegree %d, friendDegree %d, cannot step here.  Entering debugger...' % (ratingDegree, friendDegree)
                    pdb.set_trace()
                if chooseRatingGraph:
                    testUserID = None
                    while testUserID == None:
                        try:
                            testBookID = choice(ratingDict.keys())
                        except IndexError:
                            pdb.set_trace()
                        testUserID, bookTitle = userFromBook(testBookID)
                    print 'Linking via book %d (%s).\n' % (testBookID, bookTitle)
                else:
                    if friendsCollection.find({"userID": testUserID}).count() == 0:
                        # don't have this user's friends, scrape them
                        friendIDs = getFriends(sleepTime, userID)
                    else:
                        friendIDs = friendsCollection.find_one({"userID": testUserID})['friends']
                    testUserID = choice(friendIDs)
                    print 'Linking via friendship with user %d.\n' % testUserID

            if ratingsCollection.find({"userID": testUserID}).count() == 0:
                # don't have this user's ratings, scrape them
                testRatingDict = getReviews(sleepTime, testUserID)
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

# In[6]:

if __name__ == '__main__':
    # setting up mongodb

    client = MongoClient('mongodb://localhost:27017/')

    db = client['goodreads_explore_multigraph']

    friends = db['friends']
    ratings = db['reviews']
    books = db['books']

    exploreFromRecentMultigraph(ratings, friends, books, 0.05)
