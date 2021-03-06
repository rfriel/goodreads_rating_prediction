from scrape_GR_tools import *
from scrape_explore import *

import networkx as nx

def transferToFullDb(dbFull, dbFromBook):
    ratingsFull = dbFull['ratings']
    ratingsFromBook = dbFromBook['ratings']

    booksFull = dbFull['books']
    booksFromBook = dbFromBook['books']

    friendsFull = dbFull['friends']
    friendsFromBook = dbFromBook['friends']

    comms = dbFromBook['comms'].find_one()['comms']
    if len(comms) == 0:
        print 'No suitable communities found.'
    else:
        commUsers = reduce(lambda a,b: a+b, comms)

        for i, uID in enumerate(commUsers):
            r = ratingsFromBook.find_one({'userID': uID})
            if r is not None:
                if ratingsFull.find({'userID': uID}).count() == 0:
                    ratingsFull.insert_one(r)
                for bookID in r['ratings'].keys():
                    if booksFull.find({'bookID': int(bookID)}).count() == 0:
                        b = booksFromBook.find_one({'bookID': int(bookID)})
                        if b is not None:
                            booksFull.insert_one(b)
            f = friendsFromBook.find_one({'userID': uID})
            if f is not None:
                if friendsFull.find({'userID': f['userID']}).count() == 0:
                    friendsFull.insert_one(f)
            if i % 10 == 0:
                print i



def findComms(ratingsCollection, friendsCollection, booksCollection):
    # get users in graph
    userIDlist = []

    for f in friendsCollection.find():
        userIDlist.append(f['userID'])

    # make adjacency dict
    adj_dict = {}
    for f in friendsCollection.find():
        curFlist = set(f['friends'])
        friendsInData = curFlist & set(userIDlist)
        if len(friendsInData) > 0:
            adj_dict[f['userID']] = list(friendsInData)

    # make graph and get connected components
    g = nx.from_dict_of_lists(adj_dict)

    communityNodes = [nodes for nodes in nx.connected_components(g)]
    communitySizes = [len(nodes) for nodes in communityNodes]

    # make initial list of 'communities of interest'
    # defined here as connected components of size > 2 and < 30
    commsOfInterest = [(i, communitySizes[i]) for i in range(len(communitySizes))\
                   if communitySizes[i] > 2 and communitySizes[i] < 30]

    # 'reduce' the subgraphs of interest:
    # for each subgraph in commsOfInterest, prune all nodes with local clustering
    # coefficient zero, then keep the subgraph if it has any remaining nodes
    reducedCommsOfInterest = []
    for i, commIndex in enumerate(commsOfInterest):
        sg = g.subgraph(communityNodes[commIndex[0]])
        sgClustering = nx.clustering(sg)
        reducedComm = [node for node in communityNodes[commIndex[0]]\
                      if sgClustering[node] > 0]
        if len(reducedComm) > 0 and nx.number_connected_components(sg.subgraph(reducedComm)) == 1:
            reducedCommsOfInterest.append(reducedComm)

    # 'complete' the remaining subgraphs:
    # for each subgraph, add all friends of the users in the subgraph, then
    # prune the ones with local clustering coefficient zero
    completedCommsOfInterest = []
    for comm in reducedCommsOfInterest:
        commFriendsLevel1 = {f['userID']: f['friends'] \
                             for f in friendsCollection.find({'userID': {'$in': comm}})\
                            }
        graphCommFriendsLevel1 = nx.from_dict_of_lists(commFriendsLevel1)

        completedCommsOfInterest.append([node for node in graphCommFriendsLevel1.nodes() \
         if nx.clustering(graphCommFriendsLevel1)[node] > 0])

    return completedCommsOfInterest


if __name__ == '__main__':
    # setting up mongodb
    mongoClientName = "mongodb://" + sys.argv[1]
    # pass the location of your mongo client as a command line argument
    # in my project I used one of my Amazon EC2 instances and its associated storage as a central location for MongoDB

    client = MongoClient(mongoClientName)
    dbFull = client['goodreads_full']

    ratingsFull = dbFull['ratings']
    friendsFull = dbFull['friends']
    booksFull = dbFull['books']

    with open('focalbook.txt') as f:
        focalBookID = int(f.next())
        focalBookCollectionTag = f.next().rstrip()

    dbFromBook = client['goodreads_explore_from_book_' + focalBookCollectionTag]

    ratingsFromBook = dbFromBook['ratings']
    friendsFromBook = dbFromBook['friends']
    booksFromBook = dbFromBook['books']

    import pdb; pdb.set_trace()
    exploreFromBook(focalBookID, ratingsFromBook, friendsFromBook, booksFromBook, 0.05)

    completedCommsOfInterest = findComms(ratingsFromBook, friendsFromBook, booksFromBook)

    # record the communities
    dbFromBook['comms'].delete_many({}) # make sure we only have one entry in this collection
    dbFromBook['comms'].insert_one({'comms': completedCommsOfInterest, \
                                    'focalBookID': focalBookID})

    populateComms(dbFromBook, 0.05, completedCommsOfInterest)

    transferToFullDb(dbFull, dbFromBook)
