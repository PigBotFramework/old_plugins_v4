import re
import urllib.request
import urllib.error
import urllib.parse

try:
    from pyncm import apis
except ImportError:
    import pip

    pip.main(['install', "pyncm"])
    from pyncm import apis
from pbf.utils.RegCmd import RegCmd

from pbf.controller.PBF import PBF

_name = "点歌系统"
_version = "1.0.1"
_description = "点歌系统，在QQ内轻松网抑云！"
_author = "xzyStudio"
_cost = 0.00


class music(PBF):
    def get_all_hotSong(self):  # 获取热歌榜所有歌曲名称和id
        url = 'http://music.163.com/discover/toplist?id=3778678'  # 网易云云音乐热歌榜url
        header = {  # 请求头部
            'User-Agent': 'Mozilla/5.0 (X11; Fedora; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        request = urllib.request.Request(url=url, headers=header)
        html = urllib.request.urlopen(request).read().decode('utf8')  # 打开url
        html = str(html)  # 转换成str
        pat1 = r'<ul class="f-hide"><li><a href="/song\?id=\d*?">.*</a></li></ul>'  # 进行第一次筛选的正则表达式
        result = re.compile(pat1).findall(html)  # 用正则表达式进行筛选
        result = result[0]  # 获取tuple的第一个元素

        pat2 = r'<li><a href="/song\?id=\d*?">(.*?)</a></li>'  # 进行歌名筛选的正则表达式
        pat3 = r'<li><a href="/song\?id=(\d*?)">.*?</a></li>'  # 进行歌ID筛选的正则表达式
        hot_song_name = re.compile(pat2).findall(result)  # 获取所有热门歌曲名称
        hot_song_id = re.compile(pat3).findall(result)  # 获取所有热门歌曲对应的Id

        return hot_song_name, hot_song_id

    @RegCmd(
        name="热搜列表",
        usage="热搜列表[ <显示个数>]",
        permission="anyone",
        description="查看网易云热搜列表",
        mode="音乐系统"
    )
    def music_hot_search(self):
        # data = apis.playlist.GetTopPlaylists()
        # data = requests.get(self.botSettings._get('musicApi')+'search/hot/detail').json().get('data')
        data = self.get_all_hotSong()
        message = '[CQ:face,id=189] 网易云热搜列表：'

        limit = self.data.message or 10
        i = 0
        while i < int(limit):
            message += '\n[CQ:face,id=54] 歌曲名：' + str(data[0][i]) + '\n     歌曲ID：' + str(data[1][i])
            i += 1
        self.client.msg().raw(message)

    def search_music(self, song, page=1):
        return apis.cloudsearch.GetSearchResult(keyword=song, limit=self.data.botSettings._get('musicApiLimit'), offset=(page - 1) * self.data.botSettings._get('musicApiLimit')).get('result').get('songs')

    @RegCmd(
        name="搜歌 ",
        usage="搜歌 <歌曲名>[ <页数>]",
        permission="anyone",
        description="搜索歌曲，不加页数则默认为第一页",
        mode="音乐系统"
    )
    def play_music(self):
        message = self.data.message

        if ' ' in message:
            message = message.split(' ')
            i = 1
            try:
                page = int(message[-1])
            except Exception as e:
                page = 1
                i = 0
            if page != message[1]:
                num = len(message) - i
                songList = message[0:num]
                song = ''
                for i in songList:
                    song += i + ' '
            else:
                song = message[0]
        else:
            page = 1
            song = message

        self.client.msg().raw('limit={0}, offset={1}'.format(self.data.botSettings._get('musicApiLimit'), (page - 1) * self.data.botSettings._get('musicApiLimit')))

        message = '[CQ:face,id=189] 歌曲：' + str(song) + ' 的搜索结果'
        for i in self.search_music(song):
            message += '\n[CQ:face,id=54] 歌曲ID：' + str(i.get('id')) + '\n     歌曲名：' + str(
                i.get('name')) + '\n     作者：'
            for l in i.get('ar'):
                message += str(l.get('name')) + '、'
        message += '\n\n查看下一页请发送“搜歌 ' + str(song) + ' ' + str(page + 1) + '”'
        self.client.msg().raw(message)

    @RegCmd(
        name="播歌 ",
        usage="播歌 <搜歌中给出的歌曲ID或者直接加歌名>",
        permission="anyone",
        description="播放歌曲，如果后面是歌曲ID，则播放相应歌曲，如果是歌名，则会先搜索再播放第一条搜索结果",
        mode="音乐系统"
    )
    def get_music_url(self):
        message = self.data.message

        if message.isdigit():
            self.client.msg().raw('[CQ:music,type=163,id=' + str(message) + ']')
        else:
            data = self.search_music(message)
            self.client.msg().raw('[CQ:music,type=163,id=' + str(data[0]['id']) + ']')
