from scrape_GR_tools import *
from scrape_explore import *
from friend_groups import *
from modeling import *

if __name__ == '__main__':

    mongoClientName = "mongodb://" + sys.argv[1]
    # pass the location of your mongo client as a command line argument
    # in my project I used one of my Amazon EC2 instances and its associated storage as a central location for MongoDB
    
    allComms = collectAllComms(client)

    dbFull = client['goodreads_full']

    ratingsFull = dbFull['ratings']
    friendsFull = dbFull['friends']
    booksFull = dbFull['books']

    numRaters = ratingsFull.find({'userID': {'$in': [uID for comm in allComms for uID in comm]}}).count()

    for i, r in enumerate(ratingsFull.find({'userID': {'$in': [uID for comm in allComms for uID in comm]}})):
        print len(r['ratings'])
        booksToMongo(booksFull, r['userID'], r['ratings'])
        if i % 5 == 0:
            print ''
            print 100*float(i) / numRaters
            print ''
