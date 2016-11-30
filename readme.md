# Goodreads rating prediction using social network information
Robert Friel

Capstone Project, Galvanize Data Science Intensive, Fall 2016

***

Goodreads is a social networking site centering around rating and reviewing books.  Ratings are given on a discrete scale from 1 to 5 stars.  A traditional recommender system would predict unseen ratings using rating data alone.  Can these predictions be improved by leveraging information about a user's social connections?

### Community discovery

For rating prediction, we want to know about groups of linked friends.  We want the groups to be disjoint, but we also want users from multiple groups to have rated the same books, so the groups do need to be similar in some sense.

This presents a scraping challenge: as it can as much as 60 seconds or more to scrape an individual user's ratings list or friends list, a feasible random walk of the social graph (or the [friend-rating multigraph)](https://arxiv.org/abs/1008.2565 Multigraph Sampling of Online Social Networks) will only sample users very sparsely, and the resulting sample will contain few groups of mutually connected users.  With snowball sampling, one can obtain satisfactory networks surrounding individual users, but without some way of choosing these central users, it's not clear how to ensure our groups are both disjoint and similar.

The best approach I've found has been to choose a single *book*, scrape the users who made the available ratings for that book (typically ~1000 ratings are accessible to the user), and examine those users' friends lists for clusters.  `scrape_explore.py` contains functions for this procedure, as well as for the others described earlier.   `friends_groups.py` contains a pipeline for performing book-centered scraping, finding friend communities on the basis of the results, and recording the information in MongoDB databases.  The friend communities are found by a three-step process: community-like structures are identified in the raters of a specified book, these are pruned to eliminate marginal users, and the pruned groups are extended to include some users who did not rate the initial book but seem well-connected to the group.

`scrape_GR_tools.py` contains a variety of basic scraping-related functions.  The code expects text files `cookies.txt` and `focalbook.txt` in the `src` directory: the first supplies login cookies used by the scraper and the latter specifies which book to use for book-based scraping and what to name its database.

### Modeling

`modeling.py` provides functions used in `modeling.ipynb` to prepare and run ensemble models which mix a traditional factorization recommender (implemented in graphlab) with a simple model based on mean ratings in each community.
