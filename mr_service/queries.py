import base64
from mr_service import records
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore
from rdflib import URIRef, Literal
from rdflib.namespace import XSD

###############################################################################
## Queries
###############################################################################
def io_init(config):
    return SPARQLUpdateStore(
        config.SPARQL_QUERY,
        config.SPARQL_UPDATE
    )


def uri2id(uri):
    return base64.urlsafe_b64encode(uri.encode("ascii"))


def id2uri(identifier):
    return base64.urlsafe_b64decode(identifier.encode("ascii"))


def io_mark_seen(store, user_id, review_id):
    user_uri = id2uri(user_id)
    review_uri = id2uri(review_id)

    store.update(
        """
        PREFIX : <tag:ericmoritz@gmail.com,2015:vocabs/mrs#>
        INSERT DATA {{
          <{user}> :seen <{review}>
        }}
        """.format(
            user=user_uri, 
            review=review_uri
        )
    )


def sparql_to_review(r):
    return records.Review(
        r.review.toPython(),
        r.pubDate.toPython(),
        r.is_seen.toPython(),
        records.Album(
            r.album.toPython(),
            r.artist.toPython(),
            r.title.toPython()
        ),
        records.Reviewer(
            r.reviewer.toPython(),
            r.name.toPython()
        ),
        records.Rating(
            r.normalizedScore.toPython()
        )
    )


def io_top_albums(
        store, 
        user_id=None, 
        score_gte=None, 
        pub_date_gte=None
):
    if user_id:
        user_uri = URIRef(id2uri(user_id))
        use_user_uri = True
    else:
        user_uri = Literal("")
        use_user_uri = False

    if score_gte is None:
        score_gte = 80
        
    return map(
        sparql_to_review,
        store.query("""
PREFIX : <tag:ericmoritz@gmail.com,2015:vocabs/mrs#>


SELECT DISTINCT
?review ?pubDate ?album ?artist ?title ?reviewer ?name ?normalizedScore (bound(?who) as ?is_seen)
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
            user_filter_clause=(
                "FILTER ( !bound(?who) || ?who != ?user ) ." 
                if use_user_uri else ""
            ),
            pubdate_filter_clause=(
                "FILTER ( ?pubDate >= \"{pub_date}\"^^<{dt}> ) .".format(
                    pub_date=pub_date_gte,
                    dt=unicode(XSD.date)
                )
                if pub_date_gte else ""
            ),
            score_min=Literal(score_gte)
        ), 
        initBindings={
            "user": user_uri
        }
                )
    )


def io_seen_reviews(store, user_id):
    return map(
        sparql_to_review, 
        store.query(
            """
PREFIX : <tag:ericmoritz@gmail.com,2015:vocabs/mrs#>

SELECT DISTINCT ?review ?pubDate ?album ?artist ?title ?reviewer ?name ?normalizedScore (true as ?is_seen)
WHERE {
  ?review :album ?album ;
          :reviewer ?reviewer ;
          :rating ?score ;
          :pubDate ?pubDate .

  ?album :title ?title ;
         :artist ?artist .

  ?reviewer :name ?name .
  
  ?score :normalizedScore ?normalizedScore .

  ?user_id :seen ?review .
}
ORDER BY ?title ?artist
            """)
    )
