from flask import url_for, request, Flask, redirect, jsonify, g
from mr_service import queries
from functools import wraps


def abs_url_for(*args, **kwargs):
    return request.url_root.rstrip("/") + url_for(*args, **kwargs)


def _album(x):
    return {
        "artist": {
            "@type": ["Artist"],
            "name": x.artist,
        },
        "@type": ["Album"],
        "name": x.title
    }


def _reviewer(x):
    return {
        "@id": x.uri,
        "@type": ["Reviewer"],
        "name": x.name,
    }


def _rating(x):
    return {
        "@type": ["Rating"],
        "normalizedScore": x.normalizedScore
    }


def _review(collection_uri, subtype, review):
    review_id = queries.uri2id(review.uri)
    return {
        "url": review.uri,
        "@type": ["Review", subtype],
        "review_id": review_id,
        "pub_date": review.pubdate.isoformat(),
        "album": _album(review.album),
        "reviewer": _reviewer(review.reviewer),
        "rating": _rating(review.rating),
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
        "template": abs_url_for("users_queue", user_id=user_id) + "{review_id}",
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
                        "property": "pub_date",
                        "variable": "pub_date_gte",
                        "comment": "Restrict queue to items with a pub_date >= given pub_date",
                        "required": False,
                    },
                    {
                        "property": "normalizedScore",
                        "variable": "score_gte",
                        "comment": "Restrict queue to items with a rating >= given normalizedScore",
                        "required": False
                    }
                ]
            },
        }
    )
    return data


def _service_response(fun):
    @wraps(fun)
    def inner(*args, **kwargs):
        d = fun(*args, **kwargs)
        CONTEXT={
            "@vocab": abs_url_for("vocab") + "#",
            "schema": "http://schema.org/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "queue": {"@type": "@id"},
            "seen": {"@type": "@id"},
            "pub_date": {"@type": "xsd:date"},
            "name": "schema:name",
            "url": "schema:url",
            "member": "hydra:member",
            "hydra": "http://www.w3.org/ns/hydra/core#",
            "Collection": "hydra:Collection",
        }

        d.update({
            "@context": CONTEXT,
        })
            
        return jsonify(**d)
    return inner


def service(config):
    
    app = Flask("service")
    @app.before_request
    def cfg_store():
        g.store = queries.io_init(config)


    @app.route("/vocab")
    def vocab():
        return jsonify(**{
            "@context": {
                "@vocab": request.base_url,
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "hydra": "http://www.w3.org/ns/hydra/core#",
                "schema": "http://schema.org/",
            },
            "hydra:supportedClass": [
                {
                    "@id": "Review",
                    "rdfs:label": "Review",
                    "rdfs:comment": "An album review",
                    "hydra:supportedProperty": [
                        {
                            "hydra:property": {
                                "@id": "review_id",
                                "rdfs:comment": "The review's short id"
                            }
                        },
                        {
                            "hydra:property": {
                                "@id": "pub_date",
                                "rdfs:comment": "The publish date of the review",
                            },
                        },
                        {
                            "hydra:property": {
                                "@id": "album",
                                "rdfs:range": "Album"
                            },
                        },
                        {
                            "hydra:property": {
                                "@id": "reviewer",
                                "rdfs:range": "Reviewer",
                            },
                        },
                        {
                            "hydra:property": {
                                "@id": "rating",
                                "rdfs:range": "Rating"
                            }
                        }
                    ]
                },
                {
                    "@id": "Album",
                    "hydra:supportedProperty": [
                        {"hydra:property": "schema:name"},
                        {"hydra:property": {
                            "@id": "artist",
                            "rdfs:range": "Artist"
                        }},
                    ]
                },
                {
                    "@id": "Artist",
                    "hydra:supportedProperty": [
                        {"hydra:property": "schema:name"},
                    ]
                },
                {
                    "@id": "Rating",
                    "hydra:supportedProperty": [
                        {
                            "property": {
                                "@id": "normalizedScore",
                                "rdfs:comment": "The normalized score for the review, 0-100"
                            },
                        }
                    ]
                },
                {
                    "@id": "User",
                    "hydra:supportedProperty": [
                    ]
                }
            ]
        })


    @app.route("/")
    @_service_response
    def index():
        return {
            "loginForm": {
                "@type": "hydra:IriTemplate",
                "hydra:template": abs_url_for("login") + "{?user_uri}",
                "hydra:mapping": [
                    {
                        "hydra:property": "@id",
                        "hydra:variable": "user_uri",
                        "rdfs:comment": "Login with a user's URI"
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
        return _link_user(
            user_id,
            _review_list(
                request.base_url,
                "User/Seen",
                "User/Seen/Item",
                [] # TODO
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
