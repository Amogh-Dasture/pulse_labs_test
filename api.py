
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api, reqparse
from flask import Flask, make_response

from datetime import datetime, date

app=Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI']="sqlite:///discussion.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']= False
db=SQLAlchemy(app)
api=Api(app)

discussion_tag_relations = db.Table('discussion_tag_relations',
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True),
    db.Column('discussion_id', db.Integer, db.ForeignKey('discussion.id'), primary_key=True)
)

class Discussion(db.Model):
    id=db.Column(db.Integer, primary_key=True, autoincrement=True)
    text=db.Column(db.String, nullable=False)
    created_on=db.Column(db.DateTime, nullable=False)
    created_on_date=db.Column(db.Date, index=True)
    tags=db.relationship("Tag", secondary=discussion_tag_relations, back_populates="discussions")

    def __init__(self,text,created_on):
        self.text=text
        self.created_on=created_on
        self.created_on_date=created_on.date()
        super().__init__()

class Tag(db.Model):
    id=db.Column(db.Integer, primary_key=True, autoincrement=True)
    name=db.Column(db.String, nullable=False, index=True)
    discussions=db.relationship("Discussion", secondary=discussion_tag_relations, back_populates="tags")

    def __init__(self, name):
        self.name=name
        super().__init__()

def row_to_dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = str(getattr(row, column.name))
    d['tags']=[tag.name for tag in row.tags]
    return d

class DiscussionAPI(Resource):
    def __init__(self):
        self.get_reqparse=reqparse.RequestParser()
        self.get_reqparse.add_argument('query_type',type=str,choices=['tag','date','text'],required=True)

        #for tag-based search
        self.get_reqparse.add_argument('tags',type=str,action="append")

        #for date-range search
        self.get_reqparse.add_argument('start_date',type=lambda x: datetime.strptime(x,'%Y-%m-%d').date())
        self.get_reqparse.add_argument('end_date',type=lambda x: datetime.strptime(x,'%Y-%m-%d').date())

        #for text-based search
        self.get_reqparse.add_argument('search_text',type=str)

        self.post_reqparse=reqparse.RequestParser()
        self.post_reqparse.add_argument('text',type=str,required=True)
        self.post_reqparse.add_argument('tags',type=str,action="append")
        self.post_reqparse.add_argument('created_on',type=lambda x: datetime.strptime(x,'%Y-%m-%d %H:%M:%S'),required=True)

        self.put_reqparse=reqparse.RequestParser()
        self.put_reqparse.add_argument('id',type=int,required=True)
        self.put_reqparse.add_argument('text',type=str,required=True)
        self.put_reqparse.add_argument('tags',type=str,action="append")
        self.put_reqparse.add_argument('created_on',type=lambda x: datetime.strptime(x,'%Y-%m-%d %H:%M:%S'),required=True)

        self.delete_reqparse=reqparse.RequestParser()
        self.delete_reqparse.add_argument('id',type=int,required=True)
        
        super(DiscussionAPI,self).__init__()

    def get(self):
        args=self.get_reqparse.parse_args()
        if args['query_type']=='text':
            if not args['search_text']:
                return make_response('Text search query is empty',400)
            search_query='%{}%'.format(args['search_text'])
            return [row_to_dict(discussion) for discussion in Discussion.query.filter(Discussion.text.like(search_query)).order_by(Discussion.created_on.desc()).all()]

        elif args['query_type']=='date':
            if not args['start_date'] or not args['end_date']:
                return make_response('Invalid date',400)
            if args['start_date']>args['end_date']:
                return make_response('Start date greater than end date',400)
            return [row_to_dict(discussion) for discussion in Discussion.query.filter(Discussion.created_on_date.between(args['start_date'],args['end_date'])).order_by(Discussion.created_on.desc()).all()]

        elif args['query_type']=='tag':
            result=set()
            for tag_name in args['tags']:
                tag=Tag.query.filter_by(name=tag_name).first()
                result.update(tag.discussions)
            return [row_to_dict(discussion) for discussion in result]

    def post(self):
        args=self.post_reqparse.parse_args()
        if not args['text'] or not args['created_on']:
            return make_response('Bad request',400)
        newDiscussion=Discussion(text=args['text'],created_on=args['created_on'])
        for tag_name in args['tags']:
            result=Tag.query.filter_by(name=tag_name).first()
            if not result:
                newTag=Tag(name=tag_name)
                db.session.add(newTag)
                newDiscussion.tags.append(newTag)
            else:
                newDiscussion.tags.append(result)
        db.session.add(newDiscussion)
        db.session.commit()
        return row_to_dict(newDiscussion)

    def put(self):
        args=self.put_reqparse.parse_args()
        if not args['text'] or not args['created_on']:
            return make_response('Bad request',400)
        discussion=Discussion.query.get(args['id'])
        if not discussion:
            return make_response('No discussion found',404)
        discussion.tags.clear()
        discussion.text=args['text']
        discussion.created_on=args['created_on']
        for tag_name in args['tags']:
            result=Tag.query.filter_by(name=tag_name).first()
            if not result:
                newTag=Tag(name=tag_name)
                db.session.add(newTag)
                discussion.tags.append(newTag)
            else:
                discussion.tags.append(result)
        db.session.commit()
        return row_to_dict(discussion)

    def delete(self):
        args=self.delete_reqparse.parse_args()
        discussion=Discussion.query.get(args['id'])
        if not discussion:
            return make_response('No discussion found',404)
        db.session.delete(discussion)
        db.session.commit()
        return {"result":True}

api.add_resource(DiscussionAPI,'/discussion')

if(__name__=='__main__'):
   app.run()