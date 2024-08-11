from urllib import parse

import datetime
import hashlib
import random
import requests
import time
import traceback
import re
import contextlib
from pathlib import Path
import pbf.utils.nsfw.classify_nsfw as nsfw
from pbf.controller.PbfStruct import Struct
from bilibili_api import user, sync
from pbf.utils.RegCmd import RegCmd
from pbf.utils.CQCode import CQCode
from pbf.model.BiliDynamicModel import BiliDynamicModel
from pbf.model.BiliDynamicQnModel import BiliDynamicQnModel
from pbf.controller.PBF import PBF
from pbf.controller import Cache
from pbf.controller import Handler
from pbf.statement.FaceStatement import FaceStatement
from pbf.statement.TextStatement import TextStatement

try:
    import nest_asyncio

    nest_asyncio.apply()
except Exception as e:
    pass

_name = "实用功具"
_version = "1.0.1"
_description = "超多实用工具，包含近一半的指令"
_author = "xzyStudio"
_cost = 0.00


# 兽音译者，一种将“呜嗷啊~”四个字符，通过特殊算法，将明文进行重新组合的加密算法。一种新的咆哮体加密算法。还可以将四个字符任意换成其它的字符，进行加密。
# 另，可下载油猴插件Google selected text translator，https://greasyfork.org/en/scripts/36842-google-select-text-translator
# 该插件经设置后，不仅可以划词翻译兽音密文，也可生成兽音密文
class HowlingAnimalsTranslator:
    __animalVoice = "嗷呜啊~"

    def __init__(self, newAnimalVoice=None):
        self.setAnimalVoice(newAnimalVoice)

    def convert(self, txt=""):
        txt = txt.strip()
        if (txt.__len__() < 1):
            return ""
        result = self.__animalVoice[3] + self.__animalVoice[1] + self.__animalVoice[0]
        offset = 0
        for t in txt:
            c = ord(t)
            b = 12
            while (b >= 0):
                hex = (c >> b) + offset & 15
                offset += 1
                result += self.__animalVoice[int(hex >> 2)]
                result += self.__animalVoice[int(hex & 3)]
                b -= 4
        result += self.__animalVoice[2]
        return result

    def deConvert(self, txt):
        txt = txt.strip()
        if (not self.identify(txt)):
            return "Incorrect format!"
        result = ""
        i = 3
        offset = 0
        while (i < txt.__len__() - 1):
            c = 0
            b = i + 8
            while (i < b):
                n1 = self.__animalVoice.index(txt[i])
                i += 1
                n2 = self.__animalVoice.index(txt[i])
                c = c << 4 | ((n1 << 2 | n2) + offset) & 15
                if (offset == 0):
                    offset = 0x10000 * 0x10000 - 1
                else:
                    offset -= 1
                i += 1
            result += chr(c)
        return result

    def identify(self, txt):
        if (txt):
            txt = txt.strip()
            if (txt.__len__() > 11):
                if (txt[0] == self.__animalVoice[3] and txt[1] == self.__animalVoice[1] and txt[2] ==
                        self.__animalVoice[0] and txt[-1] == self.__animalVoice[2] and ((txt.__len__() - 4) % 8) == 0):
                    for t in txt:
                        if (not self.__animalVoice.__contains__(t)):
                            return False
                    return True
        return False

    def setAnimalVoice(self, voiceTxt):
        if (voiceTxt):
            voiceTxt = voiceTxt.strip()
            if (voiceTxt.__len__() == 4):
                self.__animalVoice = voiceTxt
                return True
        return False

    def getAnimalVoice(self):
        return self.__animalVoice


def getDynamic(uid):
    print("getDynamic: ", uid)

    u = user.User(int(uid))
    dynamics = []
    page = sync(u.get_dynamics())
    if 'cards' in page:
        dynamics.extend(page['cards'])
    dynamic_id = max(dynamics[0].get("desc").get("dynamic_id"), dynamics[-1].get("desc").get("dynamic_id"))
    return dynamic_id

async def screenshotDynamic(dynamic_id):
    from aunly_captcha_solver import CaptchaInfer
    from playwright.async_api import BrowserContext, async_playwright, Page

    async def get_dynamic_screenshot_mobile(dynamic_id, page: Page):
        """移动端动态截图"""
        url = f"https://m.bilibili.com/dynamic/{dynamic_id}"
        await page.set_viewport_size({"width": 460, "height": 1080})
        captcha = CaptchaInfer(
            'https://captcha-cd.ngworks.cn', 'harukabot'
        )
        page = await captcha.solve_captcha(page, url)

        await page.wait_for_load_state(state="domcontentloaded")
        await page.wait_for_selector(".b-img__inner, .dyn-header__author__face", state="visible")
        await page.add_script_tag(path=Path(__file__).parent.joinpath("mobile.js"))
        await page.wait_for_function("getMobileStyle('false')")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1000)
        await page.wait_for_function("imageComplete()")

        card = await page.query_selector(".opus-modules" if "opus" in page.url else ".dyn-card")
        assert card
        clip = await card.bounding_box()
        assert clip
        return page, clip
    

    """获取动态截图"""
    image = None
    err = ""
    filename = "{}.png".format(time.time())
    path = './resources/createimg/' + str(filename)

    for i in range(3):
        p = await async_playwright().start()
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 2560, "height": 1080},
            device_scale_factor=2,
            user_agent=(
                "Mozilla/5.0 (Linux; Android 10; RMX1911) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/100.0.4896.127 Mobile Safari/537.36"
            )
        )
        await context.add_cookies(
            [
                {
                    "name": "hit-dyn-v2",
                    "value": "1",
                    "domain": ".bilibili.com",
                    "path": "/",
                }
            ]
        )
        page = await context.new_page()
        try:
            page, clip = await get_dynamic_screenshot_mobile(dynamic_id, page)
            clip["height"] = min(clip["height"], 32766)
            await page.screenshot(clip=clip, full_page=True, type="jpeg", quality=98, path=path)
            return filename
        except TimeoutError:
            err = "截图超时"
        except AssertionError:
            err = "网页元素获取失败"
            image = await page.screenshot(full_page=True, type="jpeg", quality=80, path=path)
        except Exception as e:
            if "bilibili.com/404" in page.url:
                err = "动态不存在"
                break
            elif "waiting until" in str(e):
                err = "截图超时"
            else:
                err = "截图失败"
                with contextlib.suppress(Exception):
                    image = await page.screenshot(full_page=True, type="jpeg", quality=80, path=path)
        finally:
            with contextlib.suppress(Exception):
                await page.close()
    return filename


class tools(PBF):
    def __enter__(self):
        # 初始化BiliDynamic推送
        BiliDynamicModel(uid=227711953)
        BiliDynamicQnModel()._createTable()
        
        # 将任务添加到定时计划
        from pbf.utils import scheduler
        # [TODO] Fix bilibili sub
        # scheduler.add_job(BilibiliSub, 'interval', seconds=40, id="BilibiliSub", replace_existing=True)
        BilibiliSub()

        '''
        # 添加定时消息到计划任务
        for i in self.mysql.selectx("SELECT * FROM `botSettings`"): #marked#
            if i.get('sche') != 0:
                # and i.get('sche') > 60:
                print('scheAdd', i)
                scheduler.add_job(scheNotice, 'interval', seconds=i.get('sche'), id=f"sche{i.get('qn')}",
                                  replace_existing=True,
                                  kwargs={"qn": i.get("qn"), "content": i.get('scheContent'), "uuid": i.get("uuid")})
        '''

    @RegCmd(
        name="获取动态 ",
        usage="获取动态 <B站ID>",
        permission="anyone",
        description ="获取动态",
        mode="B 站爬虫"
    )
    def dynamic(self, echo=True):
        try:
            if echo:
                self.send("获取B站动态: {}".format(self.data.message))
            dynamic_id = getDynamic(self.data.message)
            filename = sync(screenshotDynamic(dynamic_id))
            if filename:
                self.send("[CQ:image,cache=0,file=https://pbfresources.xzynb.top/createimg/" + str(filename) + "]")
            else:
                raise ValueError("Cannot found user or dynamic")
        except Exception as e:
            self.send("emmm...找不到该用户或动态\n错误：{}".format(e))

    @RegCmd(
        name="艾特全体",
        usage="艾特全体",
        permission="admin",
        description ="艾特全体成员",
        mode="实用功能"
    )
    def atAll(self):
        dataa = self.client.CallApi('get_group_member_list', {"group_id": self.data.se.get("group_id")}).get("data")
        message = ""
        for i in dataa:
            message += "[CQ:at,qq={}]".format(i.get("user_id"))
        self.send(message)

    @RegCmd(
        name="所有表情 ",
        description="发送所有QQ表情",
        permission="owner",
        usage="所有表情 <Face ID> <Face ID>",
        mode="实用功能"
    )
    def allFaces(self):
        sta, sto = map(int, self.data.message.strip().split())
        statements = list()
        for i in range(sta, sto):
            statements.append(TextStatement(f"{i}:"))
            statements.append(FaceStatement(i))
            if i % 5 == 0:
                statements.append(TextStatement(" ", 1))
        self.client.msg(statements).send()

    @RegCmd(
        name="兽语加密 ",
        usage="兽语加密 <内容>",
        permission="anyone",
        description ="兽语加密",
        mode="兽言兽语"
    )
    def encode_shou_u(self):
        shou = HowlingAnimalsTranslator()
        self.send(shou.convert(self.data.message))

    @RegCmd(
        name="兽语解密 ",
        usage="兽语解密 <内容>",
        permission="anyone",
        description ="兽语解密",
        mode="兽言兽语"
    )
    def decode_shou_u(self):
        shou = HowlingAnimalsTranslator()
        self.send(shou.deConvert(self.data.message))

    @RegCmd(
        name="查 ",
        usage="查 <@对方>",
        permission="owner",
        description ="查询QQ绑定",
        mode="防护系统",
        hidden=1
    )
    def chaQQ(self):
        try:
            userid = self.data.message
            if 'at' in userid:
                userid = CQCode(self.data.message).get("qq")[0]
            data = requests.get('https://api.xywlapi.cc/qqapi?qq={}'.format(userid)).json()
            if data.get('status') != 200:
                return self.send('[CQ:face,id=171] 查询失败！')
            message = '[CQ:face,id=171] 用户QQ：{}\n[CQ:face,id=171] 手机号：{}\n[CQ:face,id=171] 地区：{}'.format(
                data.get('qq'), data.get('phone'), data.get('phonediqu'))
            self.send(message)
        except Exception as e:
            self.logger.warning(e, "tools.chaQQ")

    @RegCmd(
        name="插件列表",
        usage="插件列表",
        permission="anyone",
        description ="列出当前机器人本地的插件",
        mode="只因器人"
    )
    def listPlugins(self):
        message = '{0}-插件列表'.format(self.data.botSettings._get('name'))
        for i in Handler.pluginsList:
            message += '\n[CQ:face,id=147] 插件名称：' + str(i)
        # message += '\n\n所有插件均原创插件'
        self.send(message)

    @RegCmd(
        name="怼 ",
        usage="怼 <@要怼的人> <次数> <间隔时间>",
        permission="owner",
        description ="让机器人怼人",
        mode="防护系统"
    )
    def dui(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        message1 = message.split(' ')
        userid = CQCode(message1[0]).get("qq")[0]
        cishu = int(message1[1])
        jiangetime = int(message1[2])
        while cishu > 0:
            dataa = requests.get(url=self.data.botSettings._get('duiapi'))
            dataa.enconding = "utf-8"
            self.send('[CQ:at,qq=' + str(userid) + ']' + str(dataa.text))
            time.sleep(jiangetime + random.uniform(0, 2))

            cishu -= 1

    def whoonline(self):
        dataa = self.client.CallApi('get_online_clients', {})
        self.send(dataa)

    @RegCmd(
        name="戳一戳 ",
        usage="戳一戳 <@对方QQ>",
        permission="owner",
        description ="让机器人戳一戳",
        mode="只因器人"
    )
    def chuo(self):
        message = self.data.message
        message1 = CQCode(message).get("qq")[0]
        self.send('[CQ:poke,qq=' + message1 + ']')

    @RegCmd(
        name="转语音 ",
        usage="转语音 <要转语音的内容>",
        permission="owner",
        description ="将文字转为语音",
        mode="实用功能"
    )
    def zhuan(self):
        message = self.data.message
        self.send("[CQ:tts,text=" + str(message) + "]")

    @RegCmd(
        name="说 ",
        usage="说 <消息内容>",
        permission="owner",
        description ="让机器人说",
        mode="只因器人"
    )
    def echo(self):
        self.send(self.data.message)

    @RegCmd(
        name="友发 ",
        usage="友发 <要给每个好友发的消息内容>",
        permission="ro",
        description ="给机器人好友发送消息",
        mode="公告系统"
    )
    def haoyoufa(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        self.send("开始发送...")
        dataa = self.client.CallApi('get_friend_list', {})
        sum = 0
        for i in dataa.get('data'):
            if i.get('user_id') == 66600000:
                continue
            self.client.msg(message).custom(i.get("user_id"))
            self.logger.warning('好友 ' + str(i.get('nickname')) + ' 发送完毕')
            sum += 1
            time.sleep(1 + random.randint(0, 10))
        self.send('发送完毕，总好友数：' + str(sum))

    @RegCmd(
        name="群发 ",
        usage="群发 <群发内容>",
        permission="owner",
        description ="给机器人加入的群发消息",
        mode="公告系统"
    )
    def qunfa(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        # 同步公告到数据库
        self.send("同步公告...")
        formatmsg = message.replace('\n', '<br>')
        postdata = {"content": formatmsg}
        requests.post('https://pbf.xzynb.top/savenotice', data=postdata)

        self.send("开始发送...")
        try:
            dataa = self.client.CallApi('get_group_list', {})
            sum = 0
            for i in dataa.get('data'):
                self.client.msg(message).custom(uid, i.get('group_id'))
                self.logger.warning('群聊 ' + str(i.get('group_name')) + ' 发送完毕', '群发消息公告')
                time.sleep(1 + random.randint(0, 10))
                sum += 1
            self.send('发送完毕，总群聊数：' + str(sum))
        except Exception as e:
            self.send(e)

    @RegCmd(
        name="cqcode ",
        usage="cqcode <CQ的值>[ <附加参数(键值对)> ...]",
        permission="owner",
        description ="发送自定义CQ码",
        mode="只因器人"
    )
    def cqcode(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        print('init cqcode')
        message1 = message.split(' ')
        message = '[CQ:' + str(message1[0])
        for i in message1:
            if '=' in i:
                message += ',' + i
            else:
                continue
        message += ']'
        self.send(message)

    @RegCmd(
        name="md5 ",
        usage="md5 <要加密的内容>",
        permission="anyone",
        description ="MD5加密",
        mode="实用功能"
    )
    def md5(self):
        message = self.data.message
        self.send('MD5加密结果：' + str(hashlib.md5(message.encode(encoding='UTF-8')).hexdigest()))

    @RegCmd(
        name="逐字汉译英 ",
        usage="逐字汉译英 <要翻译的内容>",
        permission="anyone",
        description ="逐字逐句地翻译",
        mode="实用功能"
    )
    def twbw(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        self.send('玩命翻译中...')
        message1 = '翻译结果：'
        for i in message:
            message1 += self.utils.translator(i) + ' '
        self.send(message1)

    @RegCmd(
        name="B站搜索 ",
        usage="B站搜索 <关键词>",
        permission="anyone",
        description ="使用B站搜索，发送结果截图",
        mode="搜索系统"
    )
    def biliSearch(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        self.send('[CQ:face,id=189] 开始搜索...')
        message = message.lstrip().rstrip().replace(' ', '%20')

        self.data.message = 'https://search.bilibili.com/all?keyword=' + str(message) + ' 1 biliSearch.png'
        self.getWP(
            echo=False)  # , add_script="document.getElementsById('bili-header-container').forEach(v=>v.remove());"

    @RegCmd(
        name="必应搜索 ",
        usage="必应搜索 <关键词>",
        permission="anyone",
        description ="使用必应搜索，发送结果截图",
        mode="搜索系统"
    )
    def bingSearch(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        self.send('[CQ:face,id=189] 开始搜索...')
        message = message.lstrip().rstrip().replace(' ', '%20')

        self.data.message = 'https://cn.bing.com/search?q=' + str(message) + ' 3 bing.png'
        self.getWP(echo=False)

    @RegCmd(
        name="谷歌搜索 ",
        usage="谷歌搜索 <关键词>",
        permission="owner",
        description ="使用谷歌搜索，发送结果截图",
        mode="搜索系统"
    )
    def googleSearch(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        self.send('[CQ:face,id=189] 开始搜索...')
        message = message.lstrip().rstrip().replace(' ', '%20')

        self.data.message = 'https://www.google.com/search?q=' + str(message) + ' 1 google.png'
        self.getWP(echo=False)

    @RegCmd(
        name="百度搜索 ",
        usage="百度搜索 <关键词>",
        permission="anyone",
        description ="使用百度搜索，发送结果截图",
        mode="搜索系统"
    )
    def baiduSearch(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')
        message = self.data.message

        self.send('[CQ:face,id=189] 开始搜索...')
        message = message.lstrip().rstrip().replace(' ', '%20')

        self.data.message = 'https://baidu.com/s?word=' + str(message) + ' 1 baiduSearch.png'
        self.getWP(echo=False)
        
    @RegCmd(
        name="IAEA数据",
        usage="IAEA数据",
        permission="anyone",
        description ="获取国际原子能机构有关核废水排放的实时数据",
        mode="核废水排放"
    )
    def iaeadata(self):
        self.send('[CQ:face,id=189] 截图中...')
        self.data.message = 'https://www.iaea.org/topics/response/fukushima-daiichi-nuclear-accident/fukushima-daiichi-alps-treated-water-discharge/tepco-data 1 iaea.org.png'
        self.getWP(echo=False)

    @RegCmd(
        name="网页截图 ",
        usage="网页截图 <地址>",
        permission="owner",
        description ="给网页截图",
        mode="网页截图"
    )
    def getWP(self, echo=True, length=0, add_script=None):
        async def getScreen(filename, waittime=2, echo=True, add_script=None):
            from playwright.async_api import async_playwright
            p = await async_playwright().start()
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url)
            if add_script != None:
                await page.evaluate(add_script)
            if echo:
                self.send("网页还没加载完，再等{}秒看看".format(waittime))
            time.sleep(waittime)
            await page.screenshot(path='./resources/createimg/' + str(filename), full_page=True)
            await browser.close()

        message = self.data.message
        name = self.data.botSettings._get('name')

        #  or int(self.client.CallApi('check_url_safely', {'url':message}, timeout=20).get('data').get('level')) == 3
        try:
            if ('pornhub' in message) or ('pronhub' in message) or ('pixiv' in message):
                if echo:
                    self.send('不可以涩涩哦~')
            else:
                if message[0:7] == "http://" or message[0:8] == "https://":
                    if echo:
                        self.send('玩命截图中...')

                    waittime = 1
                    url = message
                    if ' ' in message:
                        message1 = message.split(' ')
                        url = message1[0]
                        waittime = int(message1[1])
                        filename = message[2]
                    else:
                        filename = parse.urlparse(str(message))[1] + '.png'

                    sync(getScreen(filename, waittime, echo, add_script))

                    if echo:
                        try:
                            self.send(f"什么好康的图片，让本猪先检查一下，太好看{name}是不会发出来的哦🐷")
                            nsfwPer = nsfw.main("./resources/createimg/{0}".format(filename))["nsfw"]
                            if nsfwPer >= 0.8:
                                self.send("真好看，自己去看吧，要不然我会被疼讯制裁的😭")
                        except Exception:
                            pass
                    self.send(f"[CQ:image,cache=0,file=https://pbfresources.xzynb.top/createimg/{filename}] {name}已经帮你截完图啦，这个图片来自于指定网站，不代表{name}的观点，与本猪无关哦🐷💦")
                else:
                    self.send('[CQ:face,id=147] 请使用正确的协议头！')
        except Exception as e:
            self.send('截获错误，请检查网站网址是否正确，是否可以访问\n错误信息：{}'.format(e))

    @RegCmd(
        name="翻译 ",
        usage="翻译 <目标语言>",
        permission="anyone",
        description ="翻译到任何语言（谷歌翻译）",
        mode="实用功能"
    )
    def trans(self):
        message = self.utils.translator(
            self.data.message.replace(self.data.args[1], '').strip(),
            to_lang=self.data.args[1],
            from_lang=None
        )
        # 此处如果不设置from_lang为None则to_lang为zh时就不会翻译
        self.send('[CQ:reply,id={}] {}'.format(self.data.se.get('message_id'), message))

    @RegCmd(
        name="今日人品",
        usage="今日人品",
        permission="anyone",
        description ="来看看今天人品咋样吧qwq",
        mode="装神弄鬼"
    )
    def renpin(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')

        rnd = random.Random()
        rnd.seed(int(datetime.date.today().strftime("%y%m%d")) + int(uid))
        lucknum = rnd.randint(1, 100)
        self.send('[CQ:at,qq=' + str(uid) + '] 您的今日人品为：' + str(lucknum))

    @RegCmd(
        name="BOTQG",
        usage="让机器人退群",
        permission="ro",
        description ="让机器人退群",
        mode="防护系统"
    )
    def QuiteGroup(self):
        gid = self.data.se.get('group_id')
        self.send('机器人即将退群！')
        data = self.client.CallApi('set_group_leave', {"group_id": gid})

    @RegCmd(
        name="关机",
        usage="关机",
        permission="ao",
        description ="关闭机器人",
        mode="群聊管理"
    )
    def TurnOffBot(self):
        uid = self.data.se.get('user_id')
        gid = self.data.se.get('group_id')

        self.data.groupSettings._set(power=0)
        self.send('用户 [CQ:at,qq=' + str(uid) + '] 关闭了机器人\n再见了呜呜呜，希望机器人的下一次开机~')

    @RegCmd(
        name="获取头像 ",
        usage="获取头像 <@要获取的人>",
        permission="anyone",
        description ="获取某人的头像！",
        mode="实用功能"
    )
    def getHeadImage(self):
        uid = CQCode(self.data.message).get("qq")[0]
        imgurl = f'http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100'
        self.send('[CQ:image,cache=0,url=' + imgurl + ',file=' + imgurl + ']')

    @RegCmd(
        name="运势",
        usage="运势",
        permission="anyone",
        description ="今天运势怎么样呢awa",
        mode="装神弄鬼"
    )
    def yunshi(self):
        uid = self.data.se.get('user_id')
        ob = self.data.userInfo
        if ob == None:
            return self.send('请先发送“注册”，注册后再测运势')

        if ob._get('zong') in [None, ""]:
            self.send('[CQ:face,id=147] 祈祷中...')
            shiye = random.randint(1, 100)
            taohua = random.randint(1, 100)
            cai = random.randint(1, 100)
            zong = random.randint(0, 4)
            zongarr = ['大凶', '小凶', '凶带吉', '吉带凶', '小吉', '大吉']
            zongstr = zongarr[zong]
            try:
                self.data.userInfo._set(zong=zongstr, shiye=shiye, taohua=taohua,cai=cai)
            except Exception as e:
                self.logger.warning(e, "yunshi")

            self.send(f'[CQ:face,id=147] [CQ:at,qq={uid}]您的运势：\n桃花运：{taohua}\n事业运：{shiye}\n财运：{cai}\n运势：{zongstr}')
        else:
            shiye = ob._get('shiye')
            taohua = ob._get('taohua')
            cai = ob._get('cai')
            zongstr = ob._get('zong')

            self.send(f'[CQ:face,id=147] [CQ:at,qq={uid}]\n你今天已经测过运势了喵~\n命运是不可以改变的喵~\n\>w</\n桃花运：{taohua}\n事业运：{shiye}\n财运：{cai}\n运势：{zongstr}')

    @RegCmd(
        name="生成拦截 ",
        usage="生成拦截 <要生成的网址>",
        permission="anyone",
        description ="生成qq拦截的页面",
        mode="网页截图"
    )
    def shengchenghonglian(self):
        message = self.data.message
        self.send('正在努力生成...')
        self.data.message = 'https://c.pc.qq.com/middlem.html?pfurl=' + str(message) + ' 1 shengchenghonglian.png'
        self.getWP()

    @RegCmd(
        name="B站订阅 ",
        usage="B站订阅 <B站ID>",
        permission="ao",
        description ="订阅UP猪的动态推送！",
        mode="B 站爬虫"
    )
    def addBiliSub(self):
        DynModel = BiliDynamicModel(uid=int(self.data.message))

        if not DynModel.exists:
            dynamic_id = getDynamic(self.data.message)
            DynModel._set(offset=dynamic_id)
        
        QnModel = BiliDynamicQnModel()
        if not QnModel._get(uid=self.data.message, qn=self.data.se.get("group_id")):
            QnModel._insert(uid=self.data.message, qn=self.data.se.get("group_id"), uuid=self.data.uuid)
            self.send("{}关注成功！".format(self.data.message))
        else:
            self.send("本群已关注过{}了！".format(self.data.message))

    @RegCmd(
        name="开始定时消息",
        usage="开始定时消息",
        permission="anyone",
        description ="开始定时消息\n具体消息内容及发送间隔请使用“修改设置”",
        mode="定时消息"
    )
    def startMsg(self):
        from utils import scheduler

        i = self.data.groupSettings
        print('scheContent', i._get('scheContent'))
        if i._get('sche') <= 60:
            return self.send('face54 间隔时间太短，请发送“修改设置”修改群聊设置！')
        if not i._get('scheContent'):
            return self.send('face54 未设置定时发送内容，请发送“修改设置”修改群聊设置！')
        scheduler.add_job(scheNotice, 'interval', seconds=i._get('sche'), id=f"sche{i._get('qn')}",
                          replace_existing=True,
                          kwargs={"qn": i._get("qn"), "content": i._get('scheContent'), "uuid": i._get("uuid")})

        self.send('face54 开始成功！')

    @RegCmd(
        name="B站取关 ",
        usage="B站取关 <B站ID>",
        permission="ao",
        description ="取关动态推送！",
        mode="B 站爬虫"
    )
    def delBiliSub(self):
        QnModel = BiliDynamicQnModel()
        QnModel._delete(uid=self.data.message, qn=self.data.se.get("group_id"))
        if not QnModel._get(uid=self.data.message):
            BiliDynamicModel(uid=self.data.message)._delete()
        self.send("已取关{}！".format(self.data.message))

    @RegCmd(
        name="B站关注列表",
        usage="B站关注列表",
        permission="anyone",
        description ="查看本群关注的UP猪们",
        mode="B 站爬虫"
    )
    def listBiliSub(self):
        data = BiliDynamicQnModel()._get(qn=self.data.se.get("group_id"))
        if not data:
            return self.send("本群还没有关注UP猪哦~")
        message = "face54 本群关注列表："
        for i in data:
            message += "\nUID: {}".format(i.get("uid"))
        self.send(message)

# apscheduler
def scheNotice(**kwargs):
    print('scheNotice', kwargs)
    qn, content, uuid = kwargs.get('qn'), kwargs.get('content'), kwargs.get('uuid')
    assert ((qn != None) and (content != None) and (uuid != None)), "qn, content, uuid不能为空"
    bot = PBF(Struct(se={"group_id": qn, "user_id": 2417481092}, uuid=uuid))
    time.sleep(random.randint(0, 10))
    bot.send(content)

def BilibiliSub():
    botIns = PBF(Struct())
    try:
        DynedList = []
        DynedDict = {}
        QnList = BiliDynamicQnModel()._getAll()
        for i in QnList:
            uid = i.get("uid")
            if uid not in DynedList:
                model = BiliDynamicModel(uid=uid)
                dynamic_id = getDynamic(uid)
                if str(dynamic_id) != str(model._get("offset")):
                    botIns.logger.info("find new dynamic {}".format(dynamic_id), "scheduler")
                    model._set(offset=dynamic_id)
                    filename = sync(screenshotDynamic(dynamic_id))
                    print("filename", filename)
                    DynedDict[uid] = {"filename":filename, "dynamic_id":dynamic_id}
                else:
                    DynedDict[uid] = None
                DynedList.append(uid)
            
            data = DynedDict.get(uid)
            if data != None:
                botIns.logger.info("send: {}".format(i.get("qn")), "scheduler")
                botIns.client.data.uuid = i.get("uuid")
                botIns.client.data.botSettings = None
                botIns.client.msg().custom(
                    None,
                    gid = i.get("qn"),
                    params = f"爷爷，你关注的UP猪（{uid}）发动态啦！\n[https://t.bilibili.com/{data.get('dynamic_id')}]\n[CQ:image,cache=0,file=https://pbfresources.xzynb.top/createimg/{data.get('filename')}]"
                )
            
    except Exception as e:
        botIns.logger.warning(traceback.format_exc(), "scheduler")
