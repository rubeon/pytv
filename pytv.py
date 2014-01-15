#!/usr/bin/python
import os
import sys
import traceback
# import xmlrpclib
import feedparser
import ConfigParser
import transmissionrpc
import sqlite3
import urllib2
import logging
import pprint
logging.basicConfig(filename=os.path.expanduser("~/.config/pytv.log"))
logger = logging.getLogger('transmissionrpc')
logger.setLevel(logging.INFO)

config = ConfigParser.RawConfigParser()
config.read(os.path.expanduser("~/.config/pytv.ini"))

# rss feed for torrents, showrss.info at the moment

# feed = dict(config.items('downloads'))['feed']
feed = config.get('downloads', 'feed')
ratio = config.getfloat('downloads','ratio')
print feed
print ratio

# feed = "test.xml"
# database
database_path  = os.path.expanduser("~/.config/pytv.db")

# torrent parameters
status_new = {
            0: 'stopped',
            1: 'check pending',
            2: 'checking',
            3: 'download pending',
            4: 'downloading',   
            5: 'seed pending',
            6: 'seeding',
}

status_old = {
            (1<<0): 'check pending',
            (1<<1): 'checking',
            (1<<2): 'downloading',
            (1<<3): 'seeding',
            (1<<4): 'stopped',
}

print status_new
print status_old
sys.exit(0)

# tc = transmissionrpc.Client(rpc_hostname, port=rpc_port, user=rpc_username, password=rpc_password)
tc = transmissionrpc.Client(**dict(config.items('transmission')))

def get_status(torrent):
        code = int(torrent.fields['status'])
        # print "CODE:", code
        if tc.rpc_version >= 14:
                return status_new.get(code)
        else:
                return status_old.get(code)




def create_db(conn):
        """
        creates a database, returns the sqlite object
        """
        cmd = """
        create table torrents 
                (guid text, title text, hashString text);
        """
        res = conn.execute(cmd)
        
        if res:
                logger.info("Database created: %s" % database_path )
        return res

if not os.path.exists(database_path):
        logger.warn( "Database not found, creating...")
        db = sqlite3.connect(database_path)
        create_db(db)
else:
        db = sqlite3.connect(database_path)

def get_torrents():
        """
        returns list of available torrents in the RSS feed
        """
        d = feedparser.parse(feed)
        return d

def get_active_torrents():
        """ gets list of current queue in transmission """
        res = tc.list()
        return res
        

def get_torrent_history(conn):
        """
        returns the list of all torrents ever downloaded ever
        torrents returned as list of tuples (guid, title)
        """
        cmd=""" select * from torrents """
        res=conn.execute(cmd)
        return res.fetchall()
        


def check_guid(guid):
        """
        checks if the guid is known
        """
        c = db.cursor()
        cmd = "select * from torrents where guid=?"
        c.execute(cmd, (guid,))

        if c.fetchone():
                return True
        else:
                return False
        

def save_guid(guid, torrent_name, hashString=""):
        """
        takes the guid of a torrent, and saves it to the database
        """
        c = db.cursor()
        cmd = """
        insert into torrents values (?,?,?)
        """
        c.execute(cmd, (guid, torrent_name, hashString))
        db.commit()
        return True

def add_new_torrents(torrents):
        """ Function doc """
        # print "Processing %d entires" % len(torrents.entries)
        
        for torrent in torrents.entries:
                # pprint.pprint(torrent)
                hashString = ""
                if check_guid(torrent.guid):
                        logger.info("Found %s" % torrent.guid)
                else:
                        # new content, send to transmission
                        logger.info("New: %s" % torrent.guid)
                        try:
                                res = add_torrent(torrent)
                                torrent_info = res.values()[0]
                                hashString = torrent_info.hashString
                        except transmissionrpc.TransmissionError, e:
                                logger.error( e.message)
                        except urllib2.HTTPError, e:
                                logger.error("Error retrieving %s" % torrent.guid)
                        except Exception, e:
                                traceback.print_exc()
                                break
                        save_guid(torrent.guid, torrent.title, hashString)
                                

def add_torrent(torrent):
        """ 
        sends a new torrent to the transmission daemon 
        returns tc.info() about the torrent
        """
        logger.info( "Adding %s (%s)" % (torrent.title, torrent.guid))
        if torrent.guidislink:
                torrent_uri = torrent.guid
        else:
                torrent_uri = torrent.link
        
        # get the download link
        torrent = tc.add_uri(torrent_uri)
        torrent_id = torrent.keys()[0]
        logger.debug( "add_uri returned: %s" % torrent)
        logger.debug( "Torrent ID: %s" % torrent_id )
        tc.change(torrent_id, seedRatioLimit=seed_ratio)
        res = tc.info(torrent_id)
        return res 

def cleanup_torrents():
        """
        goes through list, checking if things are done now
        """
        torrent_list = tc.list()
        for torrent in torrent_list.values():
                if get_status(torrent) in ['seeding','stopped','seed pending']:
                        # time to remove
                        logger.info( "Removing %s" % torrent.name)
                        tc.stop(torrent.id)
                        tc.remove(torrent.id)
                else:
                        logger.debug("keeping %s: %s" % (torrent.name, get_status(torrent)))
                
                
if __name__=='__main__':
        # active_torrents = get_active_torrents()
        # grab torrents from the rss feed
        torrents = get_torrents()
        # add unknown torrents from the feed to the transmission daemon
        add_new_torrents(torrents)
        # print get_torrent_history(db)
        cleanup_torrents()
        sys.exit()


