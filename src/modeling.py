from scrape_GR_tools import *
from scrape_explore import *

import graphlab as gl

from collections import defaultdict

def collectAllComms(client):
    allComms = []
    for name in client.database_names():
        if name[:28] == 'goodreads_explore_from_book_':
            print "Checking database '%s'" % name
            db = client[name]
            if db['comms'].count() != 1:
                print 'Comms collection malformed or empty: expected 1 record, found %d records' % db['comms'].count()
            else:
                comms = db['comms'].find_one()['comms']
                if len(comms) > 0:
                    for i, comm in enumerate(comms):
                        if len(comm) > 0:
                            allComms.append(comm)
                        else:
                            print "Comm %d in database '%s' was empty" % (i, name)
                print 'Database has %d comms (we now have %d in total)' % (len(comms), len(allComms))
            print ''
    print 'Finished collecting comms.  We have %d comms in total.  Pruning...\n' % len(allComms)

    allCommsPruned = []

    for i, comm1 in enumerate(allComms):
        deleteComm1 = False
        for j, comm2 in enumerate(allComms[i+1:]):
            if comm1 == comm2:
                print 'Comms %d and %d were identical; removing %d\n' % (i, j+(i+1), i)
                deleteComm1 = True
        if not deleteComm1:
            allCommsPruned.append(comm1)
    print 'Began with %d comms, now have %d after pruning.' % (len(allComms), len(allCommsPruned))
    return allCommsPruned

def getCommsOfRaters(ratingsCollection, comms):
    booksToRaterComms = defaultdict(set)
    commDict = {uID: i for i, comm in enumerate(comms) for uID in comm}

    for j, userID in enumerate(commDict.keys()):
        userComm = commDict[userID]
        r = ratingsCollection.find_one({'userID': userID})
        if r is not None:
            for bookID in r['ratings'].keys():
                booksToRaterComms[int(bookID)].add(userComm)
    return booksToRaterComms


def makeRecommenderInputs(ratingsCollection, booksCollection, comms, booksToRaterComms, \
                          bookInclusionReviewThreshold, userInclusionReviewThreshold):
    booksToInclude = set()
    usersToInclude = set()

    for r in ratingsCollection.find({'userID': {'$in': [uID for comm in comms for uID in comm]}}):
        if len(r['ratings']) >= userInclusionReviewThreshold:
            usersToInclude.add(r['userID'])

    '''
    for b in booksCollection.find({'bookID': {'$in': booksToRaterComms.keys()}}):
        raterUIDs = set([int(uID) for uID in b['ratings'].keys()])
        if len(booksToRaterComms[b['bookID']]) >= 1 and len(raterUIDs & usersToInclude) >= bookInclusionReviewThreshold:
            booksToInclude.add(b['bookID'])

    for r in ratingsCollection.find({'userID': {'$in': list(usersToInclude)}}):
        ratedBIDs = set([int(bID) for bID in r['ratings'].keys()])
        if len(ratedBIDs & booksToInclude) < userInclusionReviewThreshold:
            usersToInclude.remove(r['userID'])

    for r in ratingsCollection.find():
        curUID = r['userID']
        if curUID in allCommIDs:
            usersToInclude.add(curUID)
        else:
            usersToExclude.add(curUID)
    print '%d books excluded.' % (booksCollection.count() - len(booksToInclude))
    print '%d books included.\n' % len(booksToInclude)

    print '%d users excluded.' % (ratingsCollection.count() - len(usersToInclude))
    print '%d users included.' % len(usersToInclude)
    '''

    commDict = {uID: i for i, comm in enumerate(comms) for uID in comm}

    glRatingDict = makeRatingDictForGL(ratingsCollection, commDict, None, usersToInclude)
    glRatings = gl.SFrame(glRatingDict)

    ratingCountsByBook = glRatings.groupby(['bookID'], gl.aggregate.COUNT('rating'))
    npBookIDs = np.array(ratingCountsByBook['bookID'])
    npRatingCounts = (np.array(ratingCountsByBook['Count']))
    booksToInclude = {int(bID) for bID in npBookIDs[npRatingCounts >= bookInclusionReviewThreshold]}

    glRatingDict = makeRatingDictForGL(ratingsCollection, commDict, booksToInclude, usersToInclude)
    glRatings = gl.SFrame(glRatingDict)

    return glRatings

def makeSocialModelInputs(glRatingsTrain):
    glCommMeansTrain = glRatingsTrain.groupby(['comm'], {'meanRatingByComm': gl.aggregate.MEAN('rating')})
    glCommBookMeansTrain = glRatingsTrain.groupby(['comm', 'bookID'], {'meanBookRatingByComm': gl.aggregate.MEAN('rating')})

    commMeansTrain = {}
    commBookMeansTrain = {}

    for row in glCommMeansTrain:
        commMeansTrain[row['comm']] = row['meanRatingByComm']

    for row in glCommBookMeansTrain:
        commBookMeansTrain[(row['bookID'], row['comm'])] = row['meanBookRatingByComm']

    # the former two objects returned contain the same information as the latter two

    # the 'gl' objects are graphlab SFrames, for use as input to a graphlab recommender

    # the other two are dicts of the form {(bookID, comm): rating}, which are much
    # faster to access than the SFrames.  this speeds up predictFromCommMeans
    # a great deal.
    return glCommMeansTrain, glCommBookMeansTrain, commMeansTrain, commBookMeansTrain

def degreesOfFreedomStats(glRatingsTrain):
    nTrainObs = glRatingsTrain.shape[0]
    if 'userID' in glRatingsTrain.column_names():
        nTrainUsers = len(glRatingsTrain['userID'].unique())
    else:
        nTrainUsers = len(glRatingsTrain['comm'].unique())
    nTrainItems = len(glRatingsTrain['bookID'].unique())

    print '%d observations\n%d users\n%d books\n' % (nTrainObs, nTrainUsers, nTrainItems)

    for n in range(1,10):
        print 'A recommender with %d factor(s) (plus linear terms) would use %.1f%% of the degrees of freedom present in the data.' \
        % (n-1, 100*(n*float(nTrainUsers + nTrainItems)) / nTrainObs)
        print '(%.1f observations per model degree of freedom)\n' % (nTrainObs/(n*float(nTrainUsers + nTrainItems)))

def predictFromCommMeans(bookIDs, commIDs, commMeansTrain, commBookMeansTrain, useBookMeans):
    predictedRatings = []
    for bID, comm in zip(bookIDs, commIDs):
        if useBookMeans and ((bID, comm) in commBookMeansTrain):
            predictedRatings.append(commBookMeansTrain[(bID, comm)])
        else:
            predictedRatings.append(commMeansTrain[comm])
    return np.array(predictedRatings)

def mixedPred(glRatingsTestWithComm, commMeansTrain, commBookMeansTrain,\
              factorCommBookMeansTrain, rec_engine, rec_engine_comm, \
              commMeansOverBaseRec, socialRec, useBookMeans, meanWeight):
    preds = (1-meanWeight)*rec_engine.predict(glRatingsTestWithComm['bookID', 'userID']).to_numpy()
    if commMeansOverBaseRec:
        #
        preds += meanWeight*predictFromCommMeans(\
                                              glRatingsTestWithComm['bookID'],
                                              glRatingsTestWithComm['comm'],
                                              commMeansTrain, factorCommBookMeansTrain,
                                              useBookMeans
                                               )
    elif socialRec:
        preds += meanWeight*rec_engine_comm.predict(glRatingsTestWithComm['bookID', 'comm']).to_numpy()

    else:
        # predict community aggregates solely by retrieving relevant aggregates from a lookup table
        preds += meanWeight*predictFromCommMeans(\
                                              glRatingsTestWithComm['bookID'],
                                              glRatingsTestWithComm['comm'],
                                              commMeansTrain, commBookMeansTrain,
                                              useBookMeans
                                               )
    predRmse = rmse(preds, glRatingsTestWithComm['rating'].to_numpy())
    return preds, predRmse

def rmse(y_pred, y_true):
    sse = sum((np.array(y_pred) - np.array(y_true))**2)
    return np.sqrt(float(sse)/len(y_pred))
