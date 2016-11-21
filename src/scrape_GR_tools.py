#from selenium import webdriver
#from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup, SoupStrainer

import time
import timeit

from datetime import datetime

from pymongo import MongoClient

import requests

import cProfile
import pstats
import pdb

#import networkx as nx
#import nxpd as nxpd

import numpy as np
from random import choice

def cookies():
    valueList = []

    # expects a file named 'cookies.txt' (not provided in repo) containing
    # valid goodreads login cookies.
    #
    # when logged in on goodreads, a user gets login cookies for
    # www.goodreads.com called 'u' and 'p'.
    #
    # provide the content of these cookies in cookies.txt, with the content of
    # 'u' in the first row and the content of 'p' in the second.

    with open('cookies.txt') as f:
        for line in f:
            valueList.append(line.strip())
    return {'u': valueList[0], 'p': valueList[1]}
    '''
    return {'u': 'VX7fS6J-Gz1PR40f-p17g7wh9VjMjk9QZGMry2aJVjBdyRI0', \
          'p': 'K40nHvKlIuz-1knEFEfM755lu5S2kCE0YpLNQsjr6-SdEfm1'}
    '''

def getFriends(sleepTime, curUserID, friendCountOnly=False):
    startTime = timeit.default_timer()
    url = 'https://www.goodreads.com/friend/user/' + str(curUserID)
    #browser.get(url)
    soup = BeautifulSoup(requests.get(url,cookies=cookies()).content, 'lxml')
    #friendCount = browser.find_element_by_class_name('smallText').text
    try:
        friendCount = soup.select_one('.smallText').get_text()
    except AttributeError:
        return None

    numFriends = int(str(friendCount[friendCount.rfind(' ') +  1 : friendCount.rfind(')')]).translate(None, ','))
    if friendCountOnly:
        return numFriends

    time.sleep(sleepTime)

    friendIDs = []

    if numFriends > 0:
        perPage = min(numFriends, 600)
        curPage = 1

        while len(friendIDs) < numFriends:
            url = 'https://www.goodreads.com/friend/user/' + str(curUserID) \
                + '?page=' + str(curPage) + '&sort=first_name&per_page=' + str(perPage)

            soup = BeautifulSoup(requests.get(url,cookies=cookies()).content, 'lxml')
            friendTable = soup.find(id='friendTable')
            if friendTable is not None:
                friendHrefs = [link.get('href') for link in friendTable.findAll('a')]
                friendHrefs = filter(lambda s: s is not None, friendHrefs)
                friendComps = filter(lambda s: s[:14]=='/user/compare/', friendHrefs)
                friendIDs.extend([int(s[14:]) for s in friendComps])
                curPage += 1
                time.sleep(sleepTime)
            else:
                print 'Server choked on large page, halfing friends per page to %d . . . ' % int(perPage/2.)
                perPage = int(perPage/2)
                if perPage < 30:
                    return None
                curPage = 1
                friendIDs = []
                time.sleep(sleepTime)

    time.sleep(sleepTime)

    if len(friendIDs) != numFriends:
        print 'user %d has %d friends, but retrieved %d friends instead' % (curUserID,numFriends,len(friendIDs))

    endTime = timeit.default_timer()
    print 'Retrieved %d friends in %f seconds.' % (numFriends, endTime - startTime)

    return friendIDs




def getReviews(sleepTime, curUserID, atLeastOneRating=False):
    # this really ought to be called "getRatings"
    # TO DO ASAP: SAVE RATING DATES!!!!
    startTime = timeit.default_timer()
    ratingDict = {}

    url = 'https://www.goodreads.com/review/list/' + str(curUserID) + '?page=' + str(1) + '&print=true&shelf=read&per_page=200'

    soup = BeautifulSoup(requests.get(url,cookies=cookies()).content, 'lxml')

    try:
        curShelfString = soup.select_one('.h1Shelf').select_one('span').get_text()
    except AttributeError:
        return None
    numBooksOnCurShelf = int(str(curShelfString[curShelfString.rfind('(')+  1 : curShelfString.rfind(')')]).translate(None, ','))

    scrapeAllShelves = False
    if numBooksOnCurShelf == 0 and atLeastOneRating == True:
        # this user has rated books, but has no books on 'read' shelf, so scrape all shelves
        scrapeAllShelves = True
        url = 'https://www.goodreads.com/review/list/' + str(curUserID) + '?page=' + str(1) + '&per_page=200'
        reqOut = requests.get(url,cookies=cookies())
        soup = BeautifulSoup(reqOut.content, 'lxml')
        curShelfString = soup.select_one('.selectedShelf').get_text()
        numBooksOnCurShelf = int(str(curShelfString[curShelfString.rfind('(')+  1 : curShelfString.rfind(')')]).translate(None, ','))

    numPages = numBooksOnCurShelf/200 + 1

    headerLinks = soup.find(id='header').find_all('a')
    if headerLinks[0].find_all('img') == []:
        username = headerLinks[0].text
    else:
        username = headerLinks[1].text

    print 'Scraping %d ratings from user %d (%s)... ' % (numBooksOnCurShelf, curUserID, username)
    time.sleep(sleepTime)

    starsStrainer = SoupStrainer()


    for i in range(1, numPages+1):
        if scrapeAllShelves:
            url = 'https://www.goodreads.com/review/list/' + str(curUserID) + '?page=' + str(i) + '&print=true&per_page=200'
        else:
            url = 'https://www.goodreads.com/review/list/' + str(curUserID) + '?page=' + str(i) + '&print=true&shelf=read&per_page=200'
        #browser.get(url)
        if i > 1 or scrapeAllShelves:
            reqOut = requests.get(url,cookies=cookies())
            soup = BeautifulSoup(reqOut.content, 'lxml')
        #soup = BeautifulSoup(browser.page_source, 'lxml')
        stars = soup.select('.staticStars')
        myRatingStars = soup.select('.stars')
        dateReadField = soup.select('.field.date_read')
        dateAddedField = soup.select('.field.date_added')

        for userRating, myRating, dateRead, dateAdded in zip(stars, myRatingStars,
                                                             dateReadField[1:], dateAddedField[1:]):
            bookID = (int(myRating['data-resource-id']))
            bookRating = (len(userRating.select('.staticStar.p10')))
            bookDateRead = dateRead.find(class_='value').text.strip()
            bookDateAdded = dateAdded.find(class_='value').text.strip()

            ratingDict[bookID] = [bookRating, bookDateRead, bookDateAdded]
        time.sleep(sleepTime)

    if len(ratingDict) != numBooksOnCurShelf:
        print 'user %d has %d ratings, but retrieved %d ratings instead' % (curUserID,numBooksOnCurShelf,len(ratingDict))

    endTime = timeit.default_timer()
    print 'Retrieved %d ratings in %f seconds.' % (len(ratingDict), endTime - startTime)
    return ratingDict



def booksToMongo(booksCollection, userID, ratingDict):
    for bookID in ratingDict:
        booksCollection.update_one(
            {"bookID": bookID},
            {"$set": {"ratings." + str(userID): ratingDict[bookID]}},
            upsert=True)

def ratingsToMongo(ratingsCollection, userID, ratingDict):
    for bookID in ratingDict:
        ratingsCollection.update_one(
            {"userID": userID},
            {"$set": {"ratings." + str(bookID): ratingDict[bookID]}},
            upsert=True)

def friendsToMongo(friendsCollection, userID, friendIDs):
    # add curUserID's friends
    friendsCollection.update_one(
        {"userID": userID},
        {"$addToSet": {"friends": {"$each": friendIDs}}},
        upsert=True)

    # add curUserID to f-list of each of their friends
    # turning this off, it makes a lot of things confusing
    '''
    for friend in friendIDs:
        friendsCollection.update_one(
        {"userID": friend},
        {"$addToSet": {"friends": userID}},
        upsert=True)
    '''

def populateBooks(ratingsCollection, booksCollection, bookIDlist):
    userRows = ratingsCollection.find()
    booksNotEntered = []
    for i, row in enumerate(userRows):
        rowRatings = row['ratings']
        ratedBIDs = filter(lambda k: rowRatings[k][0] != 0, rowRatings.keys())
        userNotEntered = [int(bID) for bID in ratedBIDs if int(bID) not in bookIDlist]
        if len(userNotEntered) > 0:
            booksToMongo(books, row['userID'], row['ratings'])
            print 'Entered %d books from user %d' % (len(userNotEntered), row['userID'])
        booksNotEntered.extend(userNotEntered)
        if i % 10 == 0:
            print '%.3f%% done' % (100 * i/float(ratings.count()))
    return booksNotEntered

def snowballSample(ratingsCollection, friendsCollection, booksCollection, startID, depth, sleepTime):
    startTime = timeit.default_timer()

    searchIDs = set([startID])

    for i in range(0, depth+1):
        print 'Starting level %d...' % i
        nextLevelSearchIDs = searchIDs.copy()
        for id in searchIDs:
            #print 'Scraping user %d...' % id
            if ratingsCollection.find({"userID": id}).count() == 0:
                # don't have this user's ratings, scrape them

                ratingDict = getReviews(sleepTime, id)
                if ratingDict is not None:
                    ratingsToMongo(ratingsCollection, id, ratingDict)
                    booksToMongo(booksCollection, id, ratingDict)

            if True:# i < depth:
                if friendsCollection.find({"userID": id}).count() == 0:
                    # don't have the pre-step user's friends, scrape them
                    friendIDs = getFriends(sleepTime, id)
                    if friendIDs is not None:
                        friendsToMongo(friendsCollection, id, friendIDs)
                        nextLevelSearchIDs.update(friendIDs)
                else:
                    friendIDs = friendsCollection.find_one({"userID": id})['friends']
                    nextLevelSearchIDs.update(friendIDs)
        if i < depth:
            searchIDs = nextLevelSearchIDs

    endTime = timeit.default_timer()
    print 'Scraped %d users in %f seconds.' % (len(searchIDs), endTime - startTime)
    return searchIDs


def make_adj_dict(curUserID, friends, depth=2, friendOfFriendThreshold=0):
    adj_dict = {}
    searchIDs = set([curUserID])
    curUserFriends = set(friends.find_one({"userID": curUserID})['friends'])

    for i in range(0, depth+1):
        nextLevelSearchIDs = searchIDs.copy()
        for j, id in enumerate(searchIDs):
            if id not in adj_dict:
                curFlist = set(friends.find_one({"userID": id})['friends'])
                if i < 2 or len(curFlist & curUserFriends)> friendOfFriendThreshold:
                    adj_dict[id] = curFlist
                    nextLevelSearchIDs.update(adj_dict[id])
                if j % 1000 == 0:
                    print j
                    print len(adj_dict)
        if i < depth:
            searchIDs = nextLevelSearchIDs.copy()

def reset_colls(friendsCollection, ratingsCollection, booksCollection):
    friendsCollection.delete_many({})
    ratingsCollection.delete_many({})
    booksCollection.delete_many({})

def makeRatingDictForGL(ratingsCollection, booksToExclude=[], cutoffDate=None, upperBound=True):
    grDateFormat = '%b %d, %Y'

    userRows = ratingsCollection.find()
    glRatingDict = {'userID': [], 'bookID': [], 'rating': []}

    for row in userRows:
        ratingsField = row['ratings']
        if cutoffDate is not None:
            ratingsField = {k: v for k, v in ratingsField.items()
                        if (datetime.strptime(v[2], grDateFormat) < cutoffDate)
                        == upperBound}
        ratingsField = {k: v for k, v in ratingsField.items()
                        if int(k) not in booksToExclude}
        #ratingsField = filter(lambda r: datetime.strptime(ratingsField[r][2], grDateFormat) < cutoffDate,
        #                      ratingsField)
        ratedBIDs = filter(lambda k: ratingsField[k][0] != 0, ratingsField.keys())
        ratings = [ratingsField[bID][0] for bID in ratedBIDs]
        userIDlist = [row['userID'] for bID in ratedBIDs]

        glRatingDict['userID'].extend(userIDlist)
        glRatingDict['bookID'].extend(ratedBIDs)
        glRatingDict['rating'].extend(ratings)

    return glRatingDict

def makeRatingMatrix(ratingsCollection, booksCollection):
    userRows = ratingsCollection.find()
    userRatingMat = np.full((ratingsCollection.count(), booksCollection.count()),float('nan'))
    userIDlist = []
    bookIDlist = []

    for record in booksCollection.find(projection={'bookID': 1, '_id':0}):
        bookIDlist.append(int(record['bookID']))

    bookIDdict = {}
    for i, bookID in enumerate(bookIDlist):
        bookIDdict[bookID] = i

    for i, row in enumerate(userRows):
        userIDlist.append(row['userID'])
        rowRatings = row['ratings']
        ratedBIDs = filter(lambda k: rowRatings[k][0] != 0, rowRatings.keys())
        ratedBindices = [bookIDdict[int(bID)] for bID in ratedBIDs]
        userRatingMat[i, ratedBindices] = \
            [rowRatings[bID][0] for bID in ratedBIDs]
        if i % 100 == 0:
            print '%.3f%% done' % (100 * i/float(ratingsCollection.count()))
    return userRatingMat

def completeAdjDict(ratingsCollection, booksCollection, adj_dict, sleepTime):
    for userID in adj_dict:
        if ratingsCollection.find({"userID": userID}).count() == 0:
            ratingDict = getReviews(sleepTime, userID)
            if ratingDict is not None:
                ratingsToMongo(ratingsCollection, userID, ratingDict)
                booksToMongo(booksCollection, userID, ratingDict)
        if ratingsCollection.count() % 10 == 0:
            print '%d scraped of %d.' % (ratingsCollection.count(), len(adj_dict))

def populateComms(db, sleepTime, comms):
    ratingsCollection = db['commRatings']
    friendsCollection = db['commFriends']
    booksCollection = db['commBooks']

    for i, comm in enumerate(comms):

        for uID in comm:
            if friendsCollection.find({"userID": uID}).count() == 0:
                friendIDs = getFriends(sleepTime, uID)
                if friendIDs is not None:
                    friendsToMongo(friendsCollection, uID, friendIDs)
            if ratingsCollection.find({"userID": uID}).count() == 0:
                ratingDict = getReviews(sleepTime, uID)
                if ratingDict is not None:
                    ratingsToMongo(ratingsCollection, uID, ratingDict)
                    booksToMongo(booksCollection, uID, ratingDict)

            #snowballSample(ratingsCollection, friendsCollection, booksCollection, uID, 1, sleepTime)
