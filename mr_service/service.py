from flask import url_for, request, Flask, redirect, jsonify, g
from mr_service import queries
from functools import wraps


def abs_url_for(*args, **kwargs):
    return request.url_root.rstrip("/") + url_for(*args, **kwargs)


def _album(x):
    return {
        # schema.org fields
        "byArtist": {
            "@type": ["MusicGroup"],
            "name": x.artist,
        },
        "@type": ["MusicAlbum"],
        "name": x.title,
    }


def _reviewer(x):
    return {
        "@type": ["Person"],
        "url": x.uri,
        "name": x.name,
    }


def _rating(x):
    return {
        "@type": ["Rating"],
        "bestRating": 100,
        "worstRating": 0,
        "ratingValue": x.normalizedScore
    }


def _review(collection_uri, subtype, review):
    review_id = queries.uri2id(review.uri)
    return {
        # service fields
        "review_id": review_id,

        # schema.org fields for Review
        "url": review.uri,
        "isSeen": review.is_seen,
        "@type": ["Review", subtype],
        "datePublished": review.pubdate.isoformat(),
        "about": _album(review.album),
        "author": _reviewer(review.reviewer),
        "reviewRating": _rating(review.rating),
    }


def _review_list(request_uri, subtype, member_subtype, reviews):
    return {
        "@id": request_uri,
        "@type": ["Collection", "ReviewList", subtype],
        "member": map(
            lambda x: _review(request_uri, member_subtype, x), reviews
        )
    }

def _seen_item(user_id):
    return {
        "@type": "IriTemplate",
        "template": abs_url_for("users_seen", user_id=user_id) + "{review_id}",
        "operation": [
            {
                "@type": "DeleteResourceOperation",
                "comment": "If you delete a review into a user's seen collection, it adds it to their queue",
                "method": "DELETE"
            },
            {
                "@type": "CreateResourceOperation",
                "comment": "If you put a review into a user's seen collection, it removes it from their queue",
                "method": "PUT"
            }
        ],
        "mapping": [
            {
                "variable": "review_id",
                "property": "review_id",
                "required": True
            }
        ]
    }


def _user(user_id):
    return {
        "@id": abs_url_for("user", user_id=user_id),
        "@type": ["User"],
        "queue": abs_url_for("users_queue", user_id=user_id),
        "seen": abs_url_for("users_seen", user_id=user_id),
    }


def _link_user(user_id, data):
    data.update(
        {
            "user": _user(user_id)
        }
    )
    return data


def _link_seen_item(user_id, data):
    data.update(
        {
            "seenItem": _seen_item(user_id),
        }
    )
    return data


def _link_forms(user_id, data):
    data.update(
        {
            "queueForm": {
                "@type": "IriTemplate",
                "template": abs_url_for("users_queue", user_id=user_id) + "{?pub_date_gte,score_gte}",
                "mapping": [
                    {
                        "property": "datePublished",
                        "variable": "pub_date_gte",
                        "comment": "Restrict queue to items with a pub_date >= given pub_date",
                        "required": False,
                    },
                    {
                        "property": "ratingValue",
                        "variable": "score_gte",
                        "comment": "Restrict queue to items with a rating >= given normalizedScore",
                        "required": False
                    }
                ]
            },
        }
    )
    return data

def _context():
    return {
        "vocab": "http://rdf.vocab-ld.org/vocabs/music-reviews.jsonld#",
        "schema": "http://schema.org/",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "hydra": "http://www.w3.org/ns/hydra/core#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "comment": "rdfs:comment",

        # hydra fields
        "member": "hydra:member",
        "Collection": "hydra:Collection",
        "template": "hydra:template", 
        "mapping": "hydra:mapping",
        "property": "hydra:property",
        "variable": "hydra:variable",
        "IriTemplate": "hydra:IriTemplate",
        "operation": "hydra:operation",
        "CreateResourceOperation": "hydra:CreateResourceOperation",
        "DeleteResourceOperation": "hydra:DeleteResourceOperation",
        "method": "hydra:method",

        # service fields
        "queue": {"@id": "vocab:queue", "@type": "@id"},
        "seen": {"@id": "vocab:seen", "@type": "@id"},
        "isSeen": "vocab:isSeen",
        "loginForm": "vocab:loginForm",
        "queueForm": "vocab:queueForm", 
        "review_id": "vocab:review_id",
        "ReviewList": "vocab:ReviewList",
        "user": "vocab:user",
        "User": "vocab:User",
        "User/Queue": "vocab:User/Queue",
        "User/Queue/Item": "vocab:User/Queue/Item",
        "User/Seen": "vocab:User/Seen",
        "User/Seen/Item": "vocab:User/Seen/Item",

        # schema.org fields/classes
        "MusicGroup": "schema:MusicGroup",
        "MusicAlbum": "schema:MusicAlbum",
        "Person": "schema:Person",
        "datePublished": {"@id": "schema:datePublished","@type": "xsd:date"},
        "name": "schema:name",
        "url": "schema:url",
        "Rating": "schema:Rating",
        "bestRating": "schema:bestRating",
        "worstRating": "schema:worstRating",
        "ratingValue": "schema:ratingValue",
        "Review": "schema:Review",
        "about": "schema:about",
        "author": "schema:author",
        "byArtist": "schema:byArtist",
        "reviewRating": "schema:reviewRating",
    }
def _service_response(fun):
    @wraps(fun)
    def inner(*args, **kwargs):
        d = fun(*args, **kwargs)
        d.update({"@context": _context()})
        return jsonify(**d)
    return inner


def service(config):

    app = Flask("service")
    @app.before_request
    def cfg_store():
        g.store = queries.io_init(config)

    @app.after_request
    def cors(response):
        response.headers['Access-Control-Allow-Origin']  = "*"
        return response

    @app.route("/")
    @_service_response
    def index():
        return {
            "loginForm": {
                "@type": "IriTemplate",
                "template": abs_url_for("login") + "{?user_uri}",
                "mapping": [
                    {
                        "property": "@id",
                        "variable": "user_uri",
                        "comment": "Login with a user's URI"
                    }
                ]
            }
        }


    @app.route("/user/")
    def login():
        user_id = queries.uri2id(request.args['user_uri'])
        return redirect(
            abs_url_for("user", user_id=user_id),
            code=303
        )


    @app.route("/user/<user_id>/")
    @_service_response
    def user(user_id):
        return _user(user_id)


    @app.route("/user/<user_id>/queue/")
    @_service_response
    def users_queue(user_id):
        return _link_forms(
                user_id,
                _link_seen_item(
                    user_id,
                    _link_user(
                        user_id,
                        _review_list(
                            request.base_url,
                            "User/Queue",
                            "User/Queue/Item",
                            queries.io_top_albums(
                                g.store,
                                user_id=user_id,
                                score_gte=request.args.get("score_gte"),
                                pub_date_gte=request.args.get("pub_date_gte")
                            )
                        )
                    )
                )
            )

    @app.route("/user/<user_id>/seen/")
    @_service_response
    def users_seen(user_id):
        return _link_seen_item(
            user_id,
            _link_user(
                user_id,
                _review_list(
                    request.base_url,
                    "User/Seen",
                    "User/Seen/Item",
                    [] # TODO
                )
            )
        )


    @app.route("/user/<user_id>/seen/<review_id>", methods=["PUT"])
    @_service_response
    def put_seen(user_id, review_id):
        queries.io_mark_seen(
            g.store,
            user_id,
            review_id
        )
        return ""

    @app.route("/user/<user_id>/seen/<review_id>", methods=["DELETE"])
    @_service_response
    def delete_seen(user_id, review_id):
        user_uri = queries.id2uri(user_id)
        review_uri = queries.id2uri(review_id)
        queries.io_unseen(
            g.store,
            user_id,
            review_id
        )
        return ""
    return app
