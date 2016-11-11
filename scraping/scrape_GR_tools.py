from selenium import webdriver
from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup, SoupStrainer

import time
import timeit

from pymongo import MongoClient

import requests

import cProfile
import pstats
import pdb

import networkx as nx
import nxpd as nxpd

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
    friendIDs = []

    numFriends = int(str(friendCount[friendCount.rfind(' ') +  1 : friendCount.rfind(')')]).translate(None, ','))
    if friendCountOnly:
        return numFriends

    time.sleep(sleepTime)

    if numFriends > 0:
        url = 'https://www.goodreads.com/friend/user/' + str(curUserID) \
            + '?page=1&sort=first_name&per_page=' + str(numFriends)

        #browser.get(url)
        waitTimeCount = 0
        friendTable = None
        while friendTable == None:
            soup = BeautifulSoup(requests.get(url,cookies=cookies()).content, 'lxml')
            friendTable = soup.find(id='friendTable')
            if waitTimeCount > 0:
                print 'Server is slow, waiting %f seconds . . . ' % float(waitTimeCount*sleepTime)
                time.sleep(waitTimeCount*sleepTime)
            waitTimeCount += 1

        friendHrefs = [link.get('href') for link in friendTable.findAll('a')]

        friendHrefs = filter(lambda s: s is not None, friendHrefs)

        friendComps = filter(lambda s: s[:14]=='/user/compare/', friendHrefs)
        friendIDs.extend([int(s[14:]) for s in friendComps])

    time.sleep(sleepTime)

    if len(friendIDs) != numFriends:
        print 'user %d has %d friends, but retrieved %d friends instead' % (curUserID,numFriends,len(friendIDs))

    endTime = timeit.default_timer()
    print 'Retrieved %d friends in %f seconds.' % (numFriends, endTime - startTime)

    return friendIDs




def getReviews(sleepTime, curUserID):
    startTime = timeit.default_timer()
    ratingDict = {}

    url = 'https://www.goodreads.com/review/list/' + str(curUserID) + '?page=' + str(1) + '&print=true&shelf=read&per_page=200'
    #browser.get(url)

    #soup = BeautifulSoup(browser.page_source, 'lxml')
    reqOut = requests.get(url,cookies=cookies())
    soup = BeautifulSoup(reqOut.content, 'lxml')

    try:
        curShelfString = soup.select_one('.h1Shelf').select_one('span').get_text()
    except AttributeError:
        return None
    numBooksOnCurShelf = int(str(curShelfString[curShelfString.rfind('(')+  1 : curShelfString.rfind(')')]).translate(None, ','))
    numPages = numBooksOnCurShelf/200 + 1

    headerLinks = soup.find(id='header').find_all('a')
    if headerLinks[0].find_all('img') == []:
        username = headerLinks[0].text
    else:
        username = headerLinks[1].text

    print 'Scraping user %d (%s)... ' % (curUserID, username)
    time.sleep(sleepTime)

    starsStrainer = SoupStrainer()


    for i in range(1, numPages+1):
        url = 'https://www.goodreads.com/review/list/' + str(curUserID) + '?page=' + str(i) + '&print=true&shelf=read&per_page=200'
        #browser.get(url)
        if i > 1:
            reqOut = requests.get(url,cookies=cookies())
            soup = BeautifulSoup(reqOut.content, 'lxml')
        #soup = BeautifulSoup(browser.page_source, 'lxml')
        stars = soup.select('.staticStars')
        myRatingStars = soup.select('.stars')

        for userRating, myRating in zip(stars, myRatingStars):
            bookID = (int(myRating['data-resource-id']))
            bookRating = (len(userRating.select('.staticStar.p10')))
            ratingDict[bookID] = bookRating
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

    for friend in friendIDs:
        friendsCollection.update_one(
        {"userID": friend},
        {"$addToSet": {"friends": userID}},
        upsert=True)



def snowballSample(startID, depth, sleepTime):
    startTime = timeit.default_timer()

    searchIDs = set([startID])

    client = MongoClient('mongodb://localhost:27017/')
    db = client['goodreads']
    friends = db['friends']
    ratings = db['reviews']

    for i in range(0, depth+1):
        print 'Starting level %d...' % i
        nextLevelSearchIDs = searchIDs.copy()
        for id in searchIDs:
            #print 'Scraping user %d...' % id
            if ratings.find({"userID": id}).count() == 0:
                # don't have this user's ratings, scrape them
                pass
                #ratingDict = getReviews(sleepTime, id)
                #ratingsToMongo(ratings, id, ratingDict)

            if i < depth:
                friendIDs = getFriends(sleepTime, id)
                friendsToMongo(friends, id, friendIDs)
                # add friends to search list
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
