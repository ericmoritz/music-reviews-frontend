from flask import Flask, g, request, render_template, redirect
import os
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore, SPARQLStore
from rdflib import URIRef, Literal
from rdflib.namespace import XSD
import rdflib
from collections import namedtuple
from fp.monads.maybe import Maybe, Just

app = Flask("music-reviews")

###############################################################################
## Config
###############################################################################
Config = namedtuple("Config", ["SPARQL_QUERY", "SPARQL_UPDATE"])
config = Config(
    os.environ["SPARQL_QUERY"],
    os.environ["SPARQL_UPDATE"]
)


###############################################################################
## Records
###############################################################################
Review = namedtuple(
    "Review", 
    [ "uri", "pubdate", "album", "reviewer", "rating" ]
)
Album = namedtuple("Album", ["uri", "artist", "title"])
Reviewer = namedtuple("Reviewer", ["uri", "name"])
Rating = namedtuple("Rating", ["score"])


###############################################################################
## Queries
###############################################################################
def _mark_seen(store, user_uri, review_uri):
    # Screw SPARQL-injection concerns!
    store.update(
        """
        PREFIX : <tag:ericmoritz@gmail.com,2015:vocabs/mrs#>
        INSERT DATA {{
          <{user}> :seen <{review}>
        }}
        """.format(user=user_uri.toPython(), review=review_uri.toPython())
    )


def _query_top_albums(store, user_uri, score_min, pub_date):
    return [
        Review(
            r.review.toPython(),
            r.pubDate.toPython(),
            Album(
                r.album.toPython(),
                r.artist.toPython(),
                r.title.toPython()
            ),
            Reviewer(
                r.reviewer.toPython(),
                r.name.toPython()
            ),
            Rating(
                r.normalizedScore.toPython()
            )
        )
                
        for r in store.query("""
PREFIX : <tag:ericmoritz@gmail.com,2015:vocabs/mrs#>


SELECT DISTINCT
?review ?pubDate ?album ?artist ?title ?reviewer ?name ?normalizedScore
WHERE {{
       ?review :album ?album ;
               :reviewer ?reviewer ;
               :rating ?score ;
               :pubDate ?pubDate .

       ?album :title ?title ;
              :artist ?artist .

       ?reviewer :name ?name .

       ?score :normalizedScore ?normalizedScore .

       OPTIONAL {{ ?who :seen ?review }} .
       {user_filter_clause}
       {pubdate_filter_clause}
       FILTER ( ?normalizedScore >= {score_min} ) .

}}

ORDER BY DESC(?normalizedScore)
LIMIT 100
        """.format(
            user_filter_clause="FILTER ( !bound(?who) || ?who != ?user ) ." if user_uri.is_just else "",
            pubdate_filter_clause="FILTER ( ?pubdate > ?minPubDate ) ." if
            pub_date.is_just else "",
            score_min=score_min.default(Literal(80)).toPython()
        ), 
        initBindings={
            "user": user_uri.default(Literal("")),
            "pub_date": pub_date.default(Literal("")),
        }
    )
    ]


###############################################################################
## Service Controllers
###############################################################################
@app.before_request
def before_request():
    g.store = SPARQLUpdateStore(
        config.SPARQL_QUERY,
        config.SPARQL_UPDATE
    )


@app.route("/")
def index():

    user_uri = Maybe(request.args.get('user')).bind(
        lambda x: Just(URIRef(x))
    )

    score_min = Maybe(request.args.get('score_min')).bind(
        lambda x: Just(Literal(float(x)))
    )

    pub_date = Maybe(request.args.get('pub_date_lte')).bind(
        lambda x: Just(
            Literal(
                x,
                datatype=XSD.date
            )
        )
    )

    
    top_albums = _query_top_albums(
        g.store, 
        user_uri, 
        score_min,
        pub_date
    )


    return render_template(
        "index.html",
        members=top_albums,
        user_uri=user_uri.bind(lambda x: Just(x.toPython())),
        request_uri=request.url,
    )


@app.route("/seen")
def seen():
    user_uri = Maybe(request.args.get('user')).bind(
        lambda x: Just(URIRef(x))
    )

    review_uri = Maybe(request.args.get('review')).bind(
        lambda x: Just(URIRef(x))
    )

    user_uri.bind(
        lambda user_uri: review_uri.bind(
            lambda review_uri: _mark_seen(g.store, user_uri, review_uri)
        )
    )

    return redirect(
        request.args.get("return", "/")
    )


if __name__ == '__main__':
    app.run(
        port=int(os.environ['PORT']),
        debug=True
    )
