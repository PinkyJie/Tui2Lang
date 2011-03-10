# coding=utf-8

import urllib,re,sys
import simplejson as json
from google.appengine.ext import webapp,db
from google.appengine.ext.webapp.util import run_wsgi_app

sys.path.insert(0, 'weibopy.zip')
sys.path.append('weibopy.zip/weibopy')

from weibopy.auth import BasicAuthHandler
from weibopy.api import API
from weibopy.error import WeibopError



conf = open('config.txt')
init_params = []
for line in conf:
    if not line.startswith('#'):
        init_params.append(line.strip())

t_name, s_name, s_pass, s_app = init_params
t_timeline_url = 'http://twitter.com/statuses/user_timeline/%s.json'
re_username = re.compile(r'@([a-z|A-Z|0-9|_]+):?')
re_name_prefix = re.compile(r'@\[')
re_tag = re.compile(r'#(\w+)')
re_rt1 = re.compile(r'(RT)@')
re_rt2 = re.compile(r'(RT\s+)@')


class LastID(db.Model):
    twitter_last_id = db.StringProperty()

def replace_tweet(tweet):
    for ind,re_str in enumerate([re_username, re_tag]):
        matches = set(re_str.findall(tweet))
        if matches != ['']:
            for m in matches:
                if ind == 0:
                    tweet = tweet.replace(m, '[%s]' % m)
                elif ind == 1:
                    tweet = tweet.replace(m, '%s#' % m)
    
    for re_str in [re_rt1, re_rt2]:
        matches = set(re_str.findall(tweet))
        if matches != ['']:
            tweet = re_str.sub(unicode(' 转发自','utf8'),tweet)
    tweet = re_name_prefix.sub('[',tweet)
    return tweet

class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.out.write('TwiNa service is running now!<br>')
        last_id = LastID.get_by_key_name(s_name)
        if not last_id:
            self.response.out.write("""This is your first time to this page!<br>""")
            self.response.out.write("""TwiNa will now synchronize your last tweet!<br>""")
            auth = BasicAuthHandler(s_name,s_pass)
            api = API(auth,source=s_app)
            
            tl_file = urllib.urlopen(t_timeline_url % t_name)
            timeline = json.load(tl_file)
            tweet = replace_tweet(timeline[0]['text'])
            
            status_id = LastID(key_name=s_name)
            status_id.twitter_last_id = timeline[0]['id_str']
            status_id.put()
            
            try:
                api.update_status(tweet)
            except WeibopError,e:
                self.response.out.write(e)
            else:
                self.response.out.write('Your Last Tweet has already been synchronize:<br>')
                self.response.out.write("<b>%s</b>" % timeline[0]['text'])
            
        
class AutoSync(webapp.RequestHandler):
    def get(self):
        status_id = LastID.get_by_key_name(s_name)
        if not status_id:
            return
        tl_file = urllib.urlopen(t_timeline_url % t_name)
        timeline = json.load(tl_file)
        if isinstance(timeline,list):
            last_id = int(status_id.twitter_last_id)
            tweets_to_be_post = []
            for tl in reversed(timeline):
                if int(tl['id_str']) > last_id:
                    tweets_to_be_post.append({'id_str':tl['id_str'],'text':tl['text']})
            if len(tweets_to_be_post) > 0:
                auth = BasicAuthHandler(s_name,s_pass)
                api = API(auth,source=s_app)
                for tweet_obj in tweets_to_be_post:
                    cur_id = tweet_obj['id_str']
                    cur_tweet = tweet_obj['text']
                    if cur_tweet.find('#nosina') != -1 or cur_tweet.startswith('@'):
                        continue
                    tweet = replace_tweet(cur_tweet)
                    try:
                        api.update_status(tweet)
                        status_id.twitter_last_id = cur_id
                        status_id.put()
                    except WeibopError,e:
                        self.response.out.write(e)
                        self.response.out.write('<br>')
        else:
            self.response.out.write('Get Timeline Error!')
            
application = webapp.WSGIApplication(
                             [('/', MainPage),
                              ('/cron_sync', AutoSync)
                              ],
                             debug = True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()       