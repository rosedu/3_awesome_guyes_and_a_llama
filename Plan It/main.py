#!/usr/bin/env python
#
# Copyright 2010 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
A barebones AppEngine application that uses Facebook for login.

1.  Make sure you add a copy of facebook.py (from python-sdk/src/)
    into this directory so it can be imported.
2.  Don't forget to tick Login With Facebook on your facebook app's
    dashboard and place the app's url wherever it is hosted
3.  Place a random, unguessable string as a session secret below in
    config dict.
4.  Fill app id and app secret.
5.  Change the application name in app.yaml.

"""
FACEBOOK_APP_ID = "612116692159703"
FACEBOOK_APP_SECRET = "33e91c412cba84d2e89c8b3b7540c2fd"

import facebook
import webapp2
import os
import re
import jinja2
import urllib2
import string
import random
import datetime

from google.appengine.ext import db
from webapp2_extras import sessions


config = {}
config['webapp2_extras.sessions'] = dict(secret_key='penis')

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))

class User(db.Model):
    id = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)
    name = db.StringProperty(required=True)
    profile_url = db.StringProperty(required=True)
    access_token = db.StringProperty(required=True)
    events = db.StringProperty() #(str,indexed=True,default=[])

class Event(db.Model):
    id = db.StringProperty()
    name = db.StringProperty()
    details = db.TextProperty()
    where = db.StringProperty()
    location = db.StringProperty()
    date = db.StringProperty()
    invites = db.StringProperty()
    host = db.StringProperty()

class Location(db.Model):
    id = db.StringProperty()
    name = db.StringProperty()
    type = db.StringProperty()
    slots = db.ListProperty(int, indexed=True, default=[])

    
class BaseHandler(webapp2.RequestHandler):
    """Provides access to the active Facebook user in self.current_user

    The property is lazy-loaded on first access, using the cookie saved
    by the Facebook JavaScript SDK to determine the user ID of the active
    user. See http://developers.facebook.com/docs/authentication/ for
    more information.
    """
    @property
    def current_user(self):
        if self.session.get("user"):
            # User is logged in
            return self.session.get("user")
        else:
            # Either used just logged in or just saw the first page
            # We'll see here
            cookie = facebook.get_user_from_cookie(self.request.cookies,
                                                   FACEBOOK_APP_ID,
                                                   FACEBOOK_APP_SECRET)
            if cookie:
                # Okay so user logged in.
                # Now, check to see if existing user
                user = User.get_by_key_name(cookie["uid"])
                if not user:
                    # Not an existing user so get user info
                    graph = facebook.GraphAPI(cookie["access_token"])
                    profile = graph.get_object("me")
                    user = User(
                        key_name=str(profile["id"]),
                        id=str(profile["id"]),
                        name=profile["name"],
                        profile_url=profile["link"],
                        access_token=cookie["access_token"]
                    )
                    user.events=""
                    user.put()
                elif user.access_token != cookie["access_token"]:
                    user.access_token = cookie["access_token"]
                    user.put()
                # User is now logged in
                self.session["user"] = dict(
                    name=user.name,
                    profile_url=user.profile_url,
                    id=user.id,
                    access_token=user.access_token
                )
                return self.session.get("user")
        return None

    def dispatch(self):
        """
        This snippet of code is taken from the webapp2 framework documentation.
        See more at
        http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html

        """
        self.session_store = sessions.get_store(request=self.request)
        try:
            webapp2.RequestHandler.dispatch(self)
        finally:
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        """
        This snippet of code is taken from the webapp2 framework documentation.
        See more at
        http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html

        """
        return self.session_store.get_session()
        

class HomeHandler(BaseHandler):
    def get(self):
        template = jinja_environment.get_template('front.html')
        ev_list = []
        if(self.current_user):        
            user = db.GqlQuery("SELECT * FROM User WHERE id = '"+self.current_user['id']+"'")
            u = list(user)[0]
            if(u.events):
                events = u.events.split(',')
                for e in events:
                    if(e):
                        ev_query = db.GqlQuery("SELECT * FROM Event WHERE id = '"+ e +"'")
                        ev_list.append(list(ev_query)[0])
                    
        self.response.out.write(template.render(dict(
            facebook_app_id=FACEBOOK_APP_ID,
            current_user=self.current_user,
            events = ev_list
        )))
    def post(self):
        name = self.request.get("name")
        where = self.request.get("where")
        date = self.request.get("date")
        details = self.request.get("details")
        
        id = id_generator(10)
        e = Event()
        e.id = id
        e.name = name
        e.where = where
        e.details = details
        e.date = str(date)
        e.host = str(self.current_user['id'])

        e.put()
    
        user = db.GqlQuery("SELECT * FROM User WHERE id = '"+self.current_user['id']+"'")
        u = list(user)[0]
        u.events = u.events + "," + id
        u.put()
        
        self.redirect('/event?id='+id)
        
"""
        url = self.request.get('url')
        file = urllib2.urlopen(url)
        graph = facebook.GraphAPI(self.current_user['access_token'])
        response = graph.put_photo(file, "Test Image")
        photo_url = ("http://www.facebook.com/"
                     "photo.php?fbid={0}".format(response['id']))
        self.redirect(str(photo_url))
"""


class EventPage(BaseHandler):
    def get(self):
        id = self.request.get_all("id")
        event = db.GqlQuery("SELECT * FROM Event WHERE id = '"+ id[0] +"'")
        if event:
            event_p = list(event)[0]
            template = jinja_environment.get_template('event.html')
            """
            graph = facebook.GraphAPI(self.current_user['access_token'])
            friend_list = graph.get_connections("me", "friends");
            friends = []
            for f in friend_list['data']:
                friends.append(f['name'])
            """       
            self.response.out.write(template.render(dict(
                event = event_p, 
                current_user = self.current_user,
                editLocation = False
            )))
        else:
            self.error(404)
        
    def post(self, path):
        pass
        """
        ok_button = self.request.get('ok')
        save_button = self.request.get('save')
        edit_button = self.request.get('edit')
        id = self.request.get_all("id")
        event = db.GqlQuery("SELECT * FROM Event WHERE id = '"+ id[0] +"'")
        template = jinja_environment.get_template('event.html')
        if event:
            event_p = list(event)[0]
            if edit_button :
                editable = False
                where = self.request.get("where")
                query = db.GqlQuery("SELECT * FROM Location WHERE type = '" + where + "'")
                locations = list(query)
                stringLocations = [location.name for location in locations]
                editLocation = True
                self.response.out.write(template.render(dict(
                    event = event_p,
                    current_user = self.current_user,
                    editable = editable,
                    stringLocations = stringLocations,
                    editLocation = editLocation
                )))
            elif ok_button:
                select_answer = self.request.get('location')
                id = self.request.get_all("id")
                event.location = select_answer
                self.redirect(path)
        """     

class LogoutHandler(BaseHandler):
    def get(self):
        if self.current_user is not None:
            self.session['user'] = None

        self.redirect('/')

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_environment = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)
                               

PAGE_RE = r'(?(?:[a-zA-Z0-9_-]+/?)*)'
app = webapp2.WSGIApplication([
    ('/', HomeHandler),
    ('/logout', LogoutHandler),
    ('/event', EventPage)
    ],
    debug=True,
    config=config
)
