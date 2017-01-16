# coding: latin-1
"""
@Project Name - datpiff
@author - Johnathan
@date - 1/8/2017
@time - 3:07 PM

"""


import curses
import curses.panel
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
from collections import OrderedDict

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
        data = self.content.find('div', {'class': re.compile("awarded (diamond2x|diamond|dblplatinum|platinum|gold|silver|bronze)")})
        data = data['class']
        data = re.findall("(diamond2x|diamond|dblplatinum|platinum|gold|silver|bronze)", data)[0]
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

    def retrieve_download_link(self, download_window, screen):
        html_data = urllib.urlopen(self.url)
        html_data = BeautifulSoup.BeautifulSoup(html_data).prettify()

        # Retrieve token for to open the download/streaming window
        try:
            token = re.findall(r".*openDownload\(\s*\'(.*)\'", html_data)[0]
        except IndexError:
            download_window.addstr(7, 2, 'Something went wrong with retrieving the download token.')
            pflush()
            sleep(3)
            return None

        download_url = 'http://www.datpiff.com/pop-mixtape-download.php?id={}'.format(token)

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
            download_window.addstr(7, 2, 'Proper download url was not retrieved. Try again later.')
            pflush()
            sleep(3)
            return

    def download(self, download_window, screen):
        download_link = self.retrieve_download_link(download_window, screen)
        if not download_link:
            return False
        r = requests.get(download_link, stream=True)

        os.mkdir(self.save_path)

        chunk_size = 20480
        chunks_read = 0.0

        with open(self.full_download_path, 'wb') as f:
            total_length = int(r.headers.get('content-length'))
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    chunks_read += 1.0
                    progress = (chunks_read * 100) / (total_length / chunk_size)
                    progress = int(progress)
                    progress_str = '[{0}{1}] {2}%'.format('#' * (progress/4), ' ' * (25 - (progress/4)), progress)
                    download_window.addstr(6, 14, progress_str)
                    pflush()
                    f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())

        download_window.addstr(7, 5, 'Download successfully completed.')
        pflush()
        sleep(1)
        sys.stdout.flush()
        download_window.addstr(7, 5, 'Unzipping file.')
        pflush()
        self.unzip(download_window, screen)

    def unzip(self, download_window, screen):
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
                try:
                    song = MP3(os.path.join(self.save_path, files))
                    song.save(v1=2, v2_version=3)
                except:
                    pass

        self.cleanup(unzipped_folder, download_window, screen)

    def cleanup(self, unzipped_folder, download_window, screen):
        os.remove(self.full_download_path)
        self.full_download_path = None
        os.rmdir(unzipped_folder)

        sys.stdout.flush()
        download_window.addstr(7, 5, 'Files unzipped.')
        curses.panel.update_panels()

        screen.refresh()
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
        medal_order = ['diamond2x', 'diamond', 'dblplatinum', 'platinum', 'gold', 'silver', 'bronze']
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
                print '[{}] - [{}]\t{} by {}\t\t{}\t|\tTotal Plays: {}'.format(
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

    def download(self, sorted_num, download_window, screen):
        self.sort()
        self.sortedGroup[sorted_num].download(download_window, screen)


def get_songs(url):
    html = urllib.urlopen(url)
    soup = BeautifulSoup.BeautifulSoup(html)
    divs = soup.findAll('div', {'class': re.compile('.*awarded.*')})
    all_songs = GroupOfSongs(None)
    for x in divs:
        all_songs.add_song(Song(x))
    all_songs.sort()
    return all_songs


def make_panel(h, l, y, x, str_message, str_r=2, str_h=2, str_action=0):
    win = curses.newwin(h, l, y, x)
    win.erase()
    win.box()
    win.addstr(str_r, str_h, str_message, str_action)
    panel = curses.panel.new_panel(win)
    return win, panel


def pflush():
    curses.panel.update_panels()
    curses.doupdate()


def menu():
    loops = 0
    desired_songs = []
    current_selection = 1
    screen = curses.initscr()
    curses.cbreak()
    curses.noecho()
    curses.start_color()
    screen.keypad(True)
    filter_selection = 0
    actions = {
        'refresh':   {'command': 'r', 'help': 'Refresh current song listing.'},
        'quit':      {'command': 'q', 'help': 'Quit.'},
        'download':  {'command': 'd', 'help': 'Download currently selected songs.'},
        'select':    {'command': ' ', 'help': 'To select song, while highlighted press the space key.'},
        'help':      {'command': 'h', 'help': 'Display help menu.'}
    }
    filters = [
        ('Top Mixtapes', {'url': 'http://www.datpiff.com/mixtapes/celebrated'}),
        ('Home Page', {'url': 'http://www.datpiff.com/'}),
        ('Artist', {'url':'http://www.datpiff.com/mixtapes-search?criteria={}&sort=relevance'})
    ]
    filters = OrderedDict(filters)
    different_filter = True
    while True:
        screen.clear()
        screen.border(0)
        screen.touchwin()
        screen.refresh()
        window_h, window_x = screen.getmaxyx()
        # curses.init_pair(1, curses.COLOR_RED, curses.COLOR_WHITE)

        # Graphics Banner
        menu_graphics = [
                        '   ____      _   _____ _ ___ ___    _____ _         ',
                        '  |    \ ___| |_|  _  |_|  _|  _|  | __  |_|___ ___ ',
                        '  |  |  | .\'|  _|   __| |  _|  _|  |    -| | . |_ -|',
                        '  |____/|__,|_| |__|  |_|_| |_|    |__|__|_|  _|___|',
                        '                                           |_|      ']
        menu_graphics = [
            '  ██████╗  █████╗ ████████╗██████╗ ██╗███████╗███████╗    ██████╗ ██╗██████╗ ███████╗',
            '  ██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗██║██╔════╝██╔════╝    ██╔══██╗██║██╔══██╗██╔════╝',
            '  ██║  ██║███████║   ██║   ██████╔╝██║█████╗  █████╗      ██████╔╝██║██████╔╝███████╗',
            '  ██║  ██║██╔══██║   ██║   ██╔═══╝ ██║██╔══╝  ██╔══╝      ██╔══██╗██║██╔═══╝ ╚════██║',
            '  ██████╔╝██║  ██║   ██║   ██║     ██║██║     ██║         ██║  ██║██║██║     ███████║',
            '  ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚═╝╚═╝     ╚═╝         ╚═╝  ╚═╝╚═╝╚═╝     ╚══════╝',
            '                                                                                     '
        ]
        menu_graphics = [
                            '                                                    ',
                            '   ____      _   _____ _ ___ ___    _____ _         ',
                            '  |    \ ___| |_|  _  |_|  _|  _|  | __  |_|___ ___ ',
                            '  |  |  | .\' | _ | __ | | _ | _ | | - | |. | _ - | ',
                            '  |____/|__,|_| |__|  |_|_| |_|    |__|__|_|  _|___|',
                            '                                           |_|      '
        ]
        menu_graphics = [
            '    ___           _     ___   _    __    __     ___   _             ',
            '   |   \   __ _  | |_  | _ \ (_)  / _|  / _|   | _ \ (_)  _ __   ___',
            '   | |) | / _` | |  _| |  _/ | | |  _| |  _|   |   / | | | \'_ \ (_-<',
            '   |___/  \__,_|  \__| |_|   |_| |_|   |_|     |_|_\ |_| | .__/ /__/',
            '                                                         |_|        '
        ]
        line_num = 2
        global url
        try:
            for line in menu_graphics:
                screen.addstr(line_num, (window_x - len(line)) / 2, line[:window_x - 2], curses.A_BOLD)
                line_num += 1
        except curses.error:
            menu_graphics = ['DatPiff Rips']
            screen.addstr(line_num, (window_x - len(menu_graphics[0])) / 2, menu_graphics[0][:window_x - 2], curses.A_BOLD)

        # Determine where the filter bar is
        line_num += 2
        num_of_spaces = (window_x / (len(filters) + 1)) - (len(filters) * 2)
        first_iter = True
        for item in filters:
            if first_iter:
                if current_selection == 0 and filters[filters.keys()[filter_selection]] == filters[item]:
                    screen.addstr(line_num, 2, (' ' * num_of_spaces))
                    screen.addstr(item, curses.A_REVERSE)
                elif filters[filters.keys()[filter_selection]] == filters[item]:
                    screen.addstr(line_num, 2, (' ' * num_of_spaces))
                    screen.addstr(item, curses.A_UNDERLINE)
                else:
                    screen.addstr(line_num, 2, (' ' * num_of_spaces))
                    screen.addstr(item)
                first_iter = False
            else:
                if current_selection == 0 and filters[filters.keys()[filter_selection]] == filters[item]:
                    screen.addstr((' ' * num_of_spaces))
                    screen.addstr(item, curses.A_REVERSE)
                elif filters[filters.keys()[filter_selection]] == filters[item]:
                    screen.addstr((' ' * num_of_spaces))
                    screen.addstr(item, curses.A_UNDERLINE)
                else:
                    screen.addstr((' ' * num_of_spaces))
                    screen.addstr(item)
        # Display filter bar
        line_num += 2
        if different_filter:
            url = filters[filters.keys()[filter_selection]]['url']
            if filters.keys()[filter_selection] == 'Artist':
                artist_win_x = 60 if window_x > 90 else window_x - 20
                artist_win, artist_panel = make_panel(
                                            line_num + 3,
                                            artist_win_x,
                                            13,
                                            window_x / 2 - (artist_win_x / 2),
                                            'Artist to search:'
                )
                pflush()
                curses.echo()
                artist = screen.getstr(line_num + 6, window_x / 2 - (artist_win_x / 2) + 5, 15)
                del artist_win, artist_panel
                curses.noecho()
                url = url.format(urllib.quote(artist))
            all_songs = get_songs(url)
            all_songs.sort()
            iter_songs = all_songs.sortedGroup
            screen.touchwin()
            screen.refresh()
            different_filter = False
        # Display song listing
        line_num += 2
        for key in iter_songs:
            song_str = '[{}] [{}] {} by {}'.format(
                                ' ' if key not in desired_songs else '*',
                                iter_songs[key].medal,
                                iter_songs[key].title,
                                iter_songs[key].artist
            )[:window_x - 7]
            if key == current_selection:
                screen.addstr(line_num, 5, song_str, curses.A_REVERSE)
            else:
                screen.addstr(line_num, 5, song_str)
            line_num += 1
        screen.refresh()

        # Receive user input
        user_input = screen.getch()

        if user_input == ord(actions['quit']['command']):
            break
        elif user_input == ord(actions['select']['command']):
            if current_selection not in desired_songs:
                desired_songs.append(current_selection)
            else:
                desired_songs.remove(current_selection)
        elif user_input == ord(actions['help']['command']):
            help_win_x = 80 if window_x > 84 else window_x - 15
            help_win, help_panel = make_panel(
                                            6 + len(actions),
                                            help_win_x,
                                            8,
                                            window_x / 2 - (help_win_x / 2),
                                            'Help toolbar',
                                            2,
                                            (help_win_x - 12) / 2,
                                            curses.A_STANDOUT
            )
            for k, a in enumerate(actions):
                help_str = '{} - {}'.format(actions[a]['command'], actions[a]['help'])[:help_win_x - 5]
                help_win.addstr(4 + k, 3, help_str)
            pflush()
            screen.getch()
            del help_win, help_panel
            screen.touchwin()

        elif user_input == ord(actions['refresh']['command']):
            if window_x > 30:
                refresh_win, refresh_panel = make_panel(5, 25, 15,  (window_x - 25) / 2, 'Refreshing', 2, 7)
                pflush()

            all_songs = get_songs(url)
            iter_songs = all_songs.sortedGroup
            desired_songs = []
            current_selection = 1
            del refresh_win, refresh_panel
            pflush()

        elif user_input == ord(actions['download']['command']):
            for song in desired_songs:
                try:
                    download_win_x = 60 if window_x > 90 else window_x - 20
                    # Trims download str if its too long
                    downloading_str = 'Dl\'ing {} by {}'.format(
                                                iter_songs[song].title,
                                                iter_songs[song].artist
                    )[:download_win_x - 2]
                    downloading_win, downloading_panel = make_panel(
                        10,
                        download_win_x,
                        15,
                        window_x / 2 - (download_win_x / 2),
                        downloading_str,
                        2,
                        (download_win_x - len(downloading_str)) / 2  # Centers download string
                    )
                    pflush()
                    all_songs.download(song, downloading_win, screen)
                    del downloading_win, downloading_panel
                    pflush()
                    desired_songs = []
                    current_selection = 1
                except KeyError:
                    continue
            all_songs = get_songs(url)
            iter_songs = all_songs.sortedGroup

        elif user_input == curses.KEY_DOWN:
            if current_selection < len(iter_songs):
                current_selection += 1
            curses.endwin()

        elif user_input == curses.KEY_UP:
            if current_selection > 0:
                current_selection -= 1
            curses.endwin()

        elif user_input == curses.KEY_LEFT and current_selection == 0:
            if filter_selection > 0:
                filter_selection -= 1
                different_filter = True

        elif user_input == curses.KEY_RIGHT and current_selection == 0:
            if filter_selection < len(filters) - 1:
                filter_selection += 1
                different_filter = True

    curses.endwin()
    sys.exit(0)

def main():
    menu()

if __name__ == '__main__':
    main()
