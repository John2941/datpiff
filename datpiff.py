"""
@Project Name - main
@author - Johnathan
@date - 12/22/2016
@time - 1:41 PM

"""

import BeautifulSoup
import urllib
import re
import requests
import sys
import os
import json
from clint.textui import progress
from time import sleep
import zipfile
from socket import gethostname
from mutagen.mp3 import MP3

# Will add a .ini file for configuration settings in the future
if gethostname() == 'Johnathan-Main':
    SAVE_DIR = "E:/DatPiff Rips"
else:
    SAVE_DIR = "F:/DatPiff Rips"


class Song:
    def __init__(self, content):
        self.content = BeautifulSoup.BeautifulSoup(content.prettify())

    @property
    def medal(self):
        data = self.content.find('div', {'class': re.compile("awarded (platinum|gold|silver|bronze)")})
        data = data['class']
        data = re.findall("(platinum|gold|silver|bronze)", data)[0]
        return data

    @property
    def artist(self):
        data = self.content.find('div', {'class': 'artist'}).string
        data = data.replace('\n', '').strip()
        data = self.remove_bad_chars(data)
        return data

    @property
    def url(self):
        data = self.content.find('a')
        return 'http://www.datpiff.com/' + data['href'][1:]

    @property
    def title(self):
        data = self.content.findAll('div', {'class': 'title'})
        data = self.remove_bad_chars(data[0].text)
        return data

    @property
    def listens(self):
        data = self.content.findAll('div', {'class':'text'})
        for tag in data:
            if 'Listens' in tag.text:
                return tag.text.split(':')[-1]

    @property
    def stars(self):
        data = self.content.findAll('div', {'class':'text'})
        for tag in data:
            if 'Rating' in tag.text:
                return tag.contents[1]['alt']

    @property
    def save_path(self):
        folder_name = self.title + ' - ' + self.artist
        path = os.path.join(SAVE_DIR, folder_name)
        return path

    @property
    def download_name(self):
        download_name = self.title + ' - ' + self.artist
        download_name += '.zip'
        return download_name

    @property
    def full_download_path(self):
        return os.path.join(self.save_path, self.download_name)

    @full_download_path.setter
    def full_download_path(self, path):
        self.full_download_path = path

    @staticmethod
    def remove_bad_chars(s):
        """
        Returns the ASCII decoded version of the given HTML string. This does
        NOT remove normal HTML tags like <p>.
        /:*?"><|
        """
        bad_characters = (
            ("'", '&#39;'),
            ('"', '&quot;'),
            ('>', '&gt;'),
            ('<', '&lt;'),
            ('&', '&amp;'),
            ('-', '\\'),
            ('-', '/'),
            ('', ':'),
            ('', '*'),
            ('', '?'),
            ('', '"'),
            ('', '<'),
            ('', '>'),
            ('', '|')
        )
        for code in bad_characters:
            s = s.replace(code[1], code[0])
        return s

    def retrieve_download_link(self):
        html_data = urllib.urlopen(self.url)
        html_data = BeautifulSoup.BeautifulSoup(html_data).prettify()

        # Retrieve token for to open the download/streaming window
        try:
            token = re.findall(r".*openDownload\(\s*\'(.*)\'", html_data)[0]
        except IndexError:
            print 'Something went wrong with retrieving the download token. Try again later.'
            sleep(3)
            return None

        download_url = 'http://www.datpiff.com/pop-mixtape-download.php?id={}'.format(token)
        print 'Starting download of {} by {}.'.format(self.title, self.artist)

        # Now we must make a HTTP Post with a hidden ID to return the actual download link
        html_data = urllib.urlopen(download_url)
        html_data = BeautifulSoup.BeautifulSoup(html_data)

        hidden_id = html_data.findAll('input', {'name': 'id'})
        hidden_id = hidden_id[0]['value']

        payload = {
            'id': hidden_id,
            'x': '74',
            'y': '9'
        }

        s = requests.session()
        s = s.post('http://www.datpiff.com/download-mixtape', data=payload, allow_redirects=False)
        s = json.dumps(s.headers.__dict__['_store'])
        s = json.loads(s)
        dl_link = s['location'][1]
        if dl_link.count('http://') or dl_link.count('https://'):
            return dl_link
        else:
            print 'Proper download url was not retrieved. Try again later.'
            sleep(3)
            return

    def download(self):
        download_link = self.retrieve_download_link()
        if not download_link:
            return False
        r = requests.get(download_link, stream=True)

        os.mkdir(self.save_path)

        with open(self.full_download_path, 'wb') as f:
            total_length = int(r.headers.get('content-length'))
            for chunk in progress.bar(r.iter_content(chunk_size=20480), expected_size=(total_length/20480) + 1):
                if chunk:
                    f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())

        sys.stdout.write('\rDownload successfully completed.')
        sleep(1)
        sys.stdout.flush()
        sys.stdout.write('\rUnzipping file.' + ' ' * 45)
        self.unzip()

    def unzip(self):
        # Unzip
        zip_ref = zipfile.ZipFile(self.full_download_path)
        zip_ref.extractall(self.save_path)
        zip_ref.close()

        # Now move the songs out of their newly created parent directory
        unzipped_folder = os.path.join(self.save_path,
                                       [folder for folder in os.listdir(self.save_path)
                                        if os.path.isdir(os.path.join(self.save_path, folder))][0]
                                       )
        for files in os.listdir(unzipped_folder):
            # Deletes the unnecessary jpegs that come with the album
            if os.path.splitext(files)[1] == '.jpg':
                os.remove(os.path.join(unzipped_folder, files))
            else:
                os.rename(os.path.join(unzipped_folder, files), os.path.join(self.save_path, files))
                # This updates the song's metadata so that windows explorer will recognize it
                song = MP3(os.path.join(self.save_path, files))
                song.save(v1=2, v2_version=3)

        self.cleanup(unzipped_folder)

    def cleanup(self, unzipped_folder):
        os.remove(self.full_download_path)
        self.full_download_path = None
        os.rmdir(unzipped_folder)

        sys.stdout.flush()
        sys.stdout.write('\rFile unzipped successfully.')
        sys.stdout.flush()


class GroupOfSongs:
    def __init__(self, songs):
        if songs:
            if type(songs) is list:
                self.group = [x for x in songs]
            else:
                self.group = [songs]
        else:
            self.group = []
        self.sortedGroup = None

    def add_song(self, new_song):
        # Makes sure song isn't already in the list before appending
        if type(new_song) != list:
            new_song = [new_song]

        for new in new_song:
            if not self.is_it_owned(new):
                add_bool = True
                new_song_id = new.artist + new.title
                for old in self.group:
                    old_song_id = old.artist + old.title
                    if new_song_id == old_song_id:
                        add_bool = False
                if add_bool:
                    self.group.append(new)

    def sort(self):
        medal_order = ['platinum', 'gold', 'silver', 'bronze']
        output = {}
        sorted_dict = {}
        for song in self.group:
            if song.medal not in output.keys():
                output[song.medal] = [song]
            else:
                output[song.medal].append(song)

        for medal in medal_order:
            if medal in output.keys():
                for song in output[medal]:
                    sorted_dict[len(sorted_dict.keys()) + 1] = song

        self.sortedGroup = sorted_dict

    def print_menu(self):
        if not self.sortedGroup:
            iter_songs = self.group
            for key, song in enumerate(iter_songs):
                print '[{}] - [{}]\t{} by {}\n\t\t{}\t|\tTotal Plays: {}'.format(
                    key,
                    song.medal,
                    song.title,
                    song.artist,
                    song.stars,
                    song.listens
                )
        else:
            iter_songs = self.sortedGroup
            for key in iter_songs:
                print '[{}] - [{}]\t{} by {}\n\t\t{}\t|\tTotal Plays: {}'.format(
                    key,
                    iter_songs[key].medal,
                    iter_songs[key].title,
                    iter_songs[key].artist,
                    iter_songs[key].stars,
                    iter_songs[key].listens
                )

    @staticmethod
    def is_it_owned(song):
        list_dir = [folder for folder in os.listdir(SAVE_DIR) if os.path.isdir(os.path.join(SAVE_DIR, folder))]
        folder_name = song.title + ' - ' + song.artist
        if folder_name in list_dir:
            return True
        return False

    def download(self, sorted_num):
        self.sort()
        self.sortedGroup[sorted_num].download()


def get_songs():
    url = 'http://www.datpiff.com/'
    html = urllib.urlopen(url)
    soup = BeautifulSoup.BeautifulSoup(html)
    divs = soup.findAll('div', {'class': re.compile('.*awarded.*')})
    all_songs = GroupOfSongs(None)
    for x in divs:
        all_songs.add_song(Song(x))
    all_songs.sort()
    return all_songs


def clear():
    os.system('clear')
    print '\n\n'


def menu(all_songs):
    loops = 0
    while True:
        clear()
        if not loops:
            print('You can select multiple songs by requesting multiple numbers\n'
                  '    with spaces in between. (e.g., 1 5 12 3)\n'
                  'Missing choices mean you already have the album downloaded.\n')
        all_songs.print_menu()
        choice = raw_input('Select song: ')
        if choice.isdigit():
            choice = int(choice)
            clear()
            all_songs.download(choice)
            sleep(1)
            loops += 1
        elif choice.find(' ') > 0 and len(choice) > 2:
            choices = [int(x) for x in choice.split(' ') if x.isdigit()]
            clear()
            for song in choices:
                all_songs.download(song)
                sleep(1)
                print '\n'
            loops += 1
        elif choice.isalpha() and choice.lower() == 'q':
            print 'Quitting'
            break
        all_songs = get_songs()


def main():
    all_songs = get_songs()
    menu(all_songs)

if __name__ == '__main__':
    main()
