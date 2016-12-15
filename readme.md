# Goodreads rating prediction using social network information
Robert Friel

Capstone Project, Galvanize Data Science Intensive, Fall 2016

***

Goodreads is a social networking site centering around rating and reviewing books.  Ratings are given on a discrete scale from 1 to 5 stars.  A traditional recommender system would predict unseen ratings using rating data alone.  Can these predictions be improved by leveraging information about a user's social connections?

## Structure of this `readme` file

The first section below, ["Project Description,"](#project-description) explains the goals of this project, the technical constraints involved, and the scraping and modeling strategy used.

The second section, ["Code,"](#code) describes the  code contained in this repo and how to use it.

The third section, ["Future Work,"](#future-work) lists current issues with the code I intend to fix, and features I would like to add.

## Project Description

### Objectives

I have two potential business targets in mind.  The first, and most obvious, is book recommendation.  Goodreads currently has a recommendation feature, but at least personally I rarely find it useful.  However, I *do* discover many new books through Goodreads – through my social network on the site, which exposes me to the reviews of people with similar taste.  The fact that this strategy works so well for me (anecdotally) suggests that there is a great deal of information in Goodreads social networks that can be leveraged to make effective recommendations.

There is the risk of superfluity here: since users are already exposed continuously to reviews from their network, it is probably not helpful to additionally recommend books that their friends are already reviewing.  The goal is instead to extract latent features from social groups which can help predict how those groups would review books to which they have not yet been exposed.

The second business opportunity is targeted advertising.  In this case, the problem just mentioned may be less important: even if a user has already seen a book reviewed in their network, advertisers may wish to advertise it on their feed to reinforce name recognition or encourage the user to "take the next step" and buy the book.

### Group discovery

#### Defining friend groups

For rating prediction, we want to know about groups of linked friends.  We have some freedom in how to define these "groups," and we would like our definition to produce group distinctions with predictive value.

In principle, the groups do not need to be distinct connected components of the friendship graph (i.e. some users in one group might be friends with some users in another), and in fact do not even need to be disjoint (i.e. one user might belong to multiple groups).  But since we want group membership to provide predictive value, we would like our groups to be meaningfully different in some sense.  (As an extreme example, if we took an already-defined group and randomly assigned each member to one of two new sub-groups, we would not expect subgroup membership to have any predictive value.)

On the other hand, the groups must not be *too* dissimilar: specifically, different groups should have rated some of the same books, so that we can establish some relationship between group membership and rating for particular books.

Introducing the term "review multigraph," where two users are connected by an edge on the review multigraph for each book they have both rated, we can informally state the above as follows: "groups should be not too connected on the friendship graph, but not too disconnected on the review multigraph."

#### Scraping friend groups

Discovering friend groups via scraping is a nontrivial problem.  With Goodreads, it can take as long as 60 seconds (or more) to scrape an individual user's ratings list or friends list.  (Here, I'm scraping by sending http requests; the Goodreads API limits users to one API call per second, and I don't estimate it would be faster.)

A feasible random walk of the social graph will only sample users very sparsely, and the resulting sample will contain few groups of mutually connected users.  For instance, the image below shows a sample of users (nodes) and their friendship relations (edges) obtained from a random walk on the friend-rating multigraph, following the methodology of given in the paper [Multigraph Sampling of Online Social Networks](https://arxiv.org/abs/1008.2565) by Gjoka et. al.:

<img src="https://raw.githubusercontent.com/rfriel/goodreads_rating_prediction/master/images/social_graph_random_walk.png">

(The graph is not connected because the random walk sometimes jumped along edges on the review multigraph rather than the friendship graph.  See Gjoka et. al.  Colors distinguish connected components.)

With snowball sampling, one can obtain satisfactory networks surrounding individual users, but without some way of choosing these central users, it's not clear how to ensure that our groups have the properties we want ("not too connected on the friendship graph, but not too disconnected on the review multigraph").

The best approach I've found has been to choose a single *book*, scrape the users who made the available ratings for that book (typically ~1000 ratings are accessible to the user), and examine those users' friends lists for clusters.  The image below shows friendship relations among users who rated a particular book (Of Mice and Men), excluding users who were not friends with any others:

<img src="https://raw.githubusercontent.com/rfriel/goodreads_rating_prediction/master/images/social_graph_focal_book.png">

There is one very large connected component (center, grey).  Ignoring it for now, note that there are a number of connected components that contain some users who are all friends with one another.  Intuitively, we'd expect each of these <a href="https://en.wikipedia.org/wiki/Clique_(graph_theory)">cliques</a> to constitute part, if not all, of distinct social group (in the informal sense of the phrase).

Since these users have at least one book in common (in this case, Of Mice and Men), they are relatively likely to have other ratings in common as well.  (Choosing a more "niche" book will strengthen this similarity, at the cost of capturing a less diverse range of users.)

#### Building friend groups

Of course, the little groups in the most recent image are probably incomplete; there may be users who are key members of the groups, but just haven't rated Of Mice and Men.

To build fuller groups from these "seeds," I use the following procedure:

1. Get all connected components of the friendship graph. Remove components that are too small (2 or fewer nodes), or too large (30 or more nodes).

2. From each remaining component, make a "reduced friend group" by removing all nodes with [local clustering coefficient](https://en.wikipedia.org/wiki/Clustering_coefficient#Local_clustering_coefficient) zero.  (If no nodes remain afterwards, remove the group from consideration.)

3. Extend each "reduced friend group" by adding every friend of every user in the group.  Scrape the friends list of each added user (if we don't already have it).

4. As in step 2, remove any user with local clustering coefficient zero.  This is now the "completed friend group."

The output of step 4 ("completed friend groups") are the friend groups I use in this project, so the above procedure is my operational definition of "friend group."  A simple example of the procedure is depicted below.

<img src="https://raw.githubusercontent.com/rfriel/goodreads_rating_prediction/master/images/group_discovery.png">

The procedure (1-4) is, obviously, somewhat ad hoc and may have flaws.  I designed it in an attempt to form groups that were well-connected and did not exclude any well-connected users.  Intuitively, step 1 finds "typically sized" components, step 2 prunes off "leaf nodes" or "chains" which are not well connected to the central users, step 3 adds friends who happen not to have read the original book, and step 4 prunes off "leaf nodes" or "chains" from this extended graph.

### Modeling

This project aims to augment a traditional recommender with social information.  The traditional recommender I use is GraphLab's [`FactorizationRecommender`](https://turi.com/products/create/docs/generated/graphlab.recommender.factorization_recommender.FactorizationRecommender.html), which models an (incomplete) user-rating matrix as a sum of an overall constant term, user- and item-specific linear terms, and a low-rank factorization of the matrix (i.e. quadratic user-item interactions).  Hyperparameters are chosen via grid search, with performance evaluated using a test-train split.  (Test-train splits are generated with GraphLab's [`random_split_by_user`](https://turi.com/products/create/docs/generated/graphlab.recommender.util.random_split_by_user.html) method, which forms specialized test-train splits for recommender systems.)

I have tried a variety of approaches to friend group-based prediction.  The basic framework is a two-member ensemble method, with predicted ratings given by a linear combination of the traditional recommender's prediction and the prediction of some group-based model (which uses only group membership, and knows nothing about a user except for which group they are in).  That is, for some &lambda;, the prediction is &lambda; times the traditional recommender's prediction plus (1-&lambda;) times the group-based model's prediction.

For the group-based models (or "social models"), I have tried the following (among others), listed in order of complexity:

1. For (user in) group `i` and book `j`, simply predict the average rating given by users in group `i` (across all books they rated).

2. For (user in) group `i` and book `j`, predict the average rating given by users in group `i` to book `j`.  If no one in group `i` has rated book `j`, default to Model 1 above.

3. Train a separate `FactorizationRecommender` for groups, where each group is a "user," and each book rating is the average rating given to that book by users in the group (if it exists).

In the tests I have performed, the more complex of these models are worse: social model 1 performs better than 2, which performs better than 3 (over the hyperparameters I have tried).  By "performance" here, I mean the performance of the corresponding ensemble method, when the optimal &lambda; for the given social model is chosen.

This result is not very satisfying given the initial motivations of the project, as Model 1 cannot predict group-book interactions.  It merely says, "you are likely to give high (or low) ratings, because your social group does."  This information is of little use to the user, although it might be useful for establishing "less biased" rating averages for individual books.

### Model performance

The results below were computed using a data set containing 78 friend groups, obtained by scraping ratings from 11 books<sup id="booklistFnTop">[1](#booklistFn)</sup>.

In the image below, the blue curve shows the performance (RMSE) of the ensemble model, using social model 1, across a range of &lambda; values (horizontal axis).

The green curves are results from a test meant to check whether the social information was really providing predictive value.  To check this, I assigned users randomly to 78 "fake" groups, of the same sizes as the 78 actual groups.  The social model then made predictions as though these were the actual groups.  The 30 green curves come from 30 different random assignments, across 3 different test-train splits (10 per split).

In general, these models performed nearly as well as the actual-group model.  This is surprising, since these models are effectively just adding (a type of) regularization to the traditional recommender; either I hadn't found the best regularization hyperparameters for the traditional recommender, or the (different) regularization provided by these models in some way supplements the L2 regularization provided by GraphLab.

Nonetheless, the actual-group social model (blue curve) was superior to these "fake" models.

<img src="https://raw.githubusercontent.com/rfriel/goodreads_rating_prediction/master/images/model_performance.png">

<a name="booklistFn" href="#booklistFnTop">1</a>: The books were: Ender's Game, The Elegance of the Hedgehog, Pride and Prejudice, Of Mice and Men, Infinite Jest, The Alchemist, House of Leaves, The Sun Also Rises, A Game of Thrones, Atlas Shrugged, and The Communist Manifesto.

## Code

### Overview

Dependencies:

* Beautiful Soup 4
* pymongo
* networkx

Optional dependencies:

* GraphLab (required for modeling, but not for scraping and group discovery)

Scraping is performed using the `requests` module and Beautiful Soup.  Scraped data and friend groups are stored in a MongoDB database using pymongo.  Graph theory computations are done with networkx.  GraphLab is used for factorization recommenders.

In general, the code is not as well-organized as I would like it to be.  It was written quickly for a 2.5-week project.  I plan to add more documentation to the code in the future.

Currently, the core functionality is in a set of python files, and my exploratory work is in a set of jupyter notebooks.  The jupyter notebooks are not very readable at this point.

### Files

The python script `friends_groups.py` performs scraping and group discovery process.  It takes a command-line argument specifying the location of the MongoDB server.  It expects to be run from the `src` directory, and expects that directory to contain two text files, `cookies.txt` and `focalbook.txt`: the first supplies login cookies used by the scraper and the latter specifies which book to use for book-based scraping and what to name its database.

`scrape_explore.py` contains functions for exploring the friend-rating multigraph in various ways.

`friends_groups.py` contains a pipeline for performing book-centered scraping, finding friend communities on the basis of the results, and recording the information in MongoDB databases.

`scrape_GR_tools.py` contains a variety of basic scraping-related functions.

`modeling.py` provides functions to prepare and run ensemble models.  `modeling.ipynb` contains the modeling tests I have done so far.

## Future Work

Includes, but is not limited to:

* Think further about the procedure for generating friend groups and the design of the social models, and possibly add variants to the code.

* Add descriptions of each code file to the start of that file.

* Improve code flow and readability.

* Clean up `modeling.ipynb` so that my exploratory modeling work can be easily read and understood by others.

* Build models that forecast later ratings on the basis of past ones.  (There is code in place to split up ratings in this fashion, but the friend groups are generated from the latest friendship data, so they would leak information from the future.  Allow the friendship graph to be rolled back to an arbitrary past date, if this is possible.)
