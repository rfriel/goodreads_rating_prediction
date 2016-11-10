
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
    nRatings = int(soup.find_all(itemprop="ratingCount")[0].get('title'))

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


# In[4]:

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
                try:
                    testBookID = choice(ratingDict.keys())
                except IndexError:
                    pdb.set_trace()
                testUserID = None
                while testUserID == None:
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


# In[6]:

if __name__ == '__main__':
    # setting up mongodb

    client = MongoClient('mongodb://localhost:27017/')

    db = client['goodreads_explore']

    friends = db['friends']
    ratings = db['reviews']
    books = db['books']

    exploreFromRecent(ratings, friends, books, 0.05)
