import json
import random
import time

from pbf.controller.PBF import PBF
from pbf.utils.RegCmd import RegCmd
from pbf.model.MCModel import MCModel
from pbf.statement.TextStatement import TextStatement
from pbf.statement.FaceStatement import FaceStatement

_name = "MC小游戏"
_version = "1.0.1"
_description = "在QQ群内玩MC小游戏"
_author = "xzyStudio"
_cost = 0.00


class mc(PBF):
    userItem = []
    makeTable = {
        "木镐": [{"name": "原木", "count": 2}],
        "石镐": [{"name": "原木", "count": 1}, {"name": "圆石", "count": 3}],
        "铁镐": [{"name": "原木", "count": 1}, {"name": "铁锭", "count": 3}],
        "金镐": [{"name": "原木", "count": 1}, {"name": "金锭", "count": 3}],
        "钻石镐": [{"name": "原木", "count": 1}, {"name": "钻石", "count": 3}],
        "木剑": [{"name": "原木", "count": 2}],
        "石剑": [{"name": "原木", "count": 1}, {"name": "圆石", "count": 2}],
        "铁剑": [{"name": "原木", "count": 1}, {"name": "铁锭", "count": 2}],
        "金剑": [{"name": "原木", "count": 1}, {"name": "金锭", "count": 2}],
        "钻石剑": [{"name": "原木", "count": 1}, {"name": "钻石", "count": 1}],
        "金苹果": [{"name": "金锭", "count": 72}],
        "鱼竿": [{"name": "原木", "count": 2}, {"name": "线", "count": 2}],
        "TNT": [{"name": "原木", "count": 5}, {"name": "火药", "count": 4}]
    }
    eatList = {
        "猪肉": 1,
        "小麦": 1,
        "金苹果": 5
    }
    killList = {
        "木剑": 2,
        "石剑": 3,
        "铁剑": 4,
        "金剑": 6,
        "钻石剑": 5,
        "TNT": 15
    }

    def init(self):
        self.user = MCModel(qn=self.data.se.get("user_id"))
        if self.user.exists:
            self.userItem = self.user._getAll()
            try:
                self.userItem['backpack'] = json.loads(self.userItem.get('backpack'))
            except Exception:
                pass
        else:
            self.userItem = False
            self.user._delete()

    def die(self):
        MCModel(qn=self.data.se.get("user_id"))._delete()

    def getKill(self, thi):
        if "镐" in thi:
            return 2
        return self.killList.get(thi) if self.killList.get(thi) else 1

    def getProtect(self):
        pass

    def addLife(self, num=1):
        self.userItem['life'] += num
        self.user._set(life=self.userItem.get("life"))

    def addXp(self, num=1):
        self.userItem['xp'] += num
        self.user._set(xp=self.userItem.get("xp"))

    def randomXp(self, low=1, high=10):
        xp = random.randint(low, high)
        self.addXp(xp)
        return xp

    def getBackpack(self, thi):
        return self.userItem.get("backpack").get(thi) if self.userItem.get("backpack").get(thi) else 0

    def addBackpack(self, thi, num=1):
        if self.userItem.get("backpack").get(thi):
            self.userItem['backpack'][thi] += num
        else:
            self.userItem['backpack'][thi] = num
        self.userItem["backpack"][thi] = self.userItem.get("backpack").get(thi) if self.userItem.get("backpack").get(
            thi) >= 0 else 0
        self.user._set(backpack=json.dumps(self.userItem.get("backpack"), ensure_ascii=False))
        self.userItem['backpack'] = json.loads(self.userItem.get('backpack'))
        print("3", self.userItem.get("backpack"), type(self.userItem.get("backpack")))

    def addEvent(self, doing, utill):
        self.user._set(doing=doing, doingutill=utill)

    def ifDoing(self):
        return True if (self.userItem.get("doing") and self.userItem.get("doingutill")) and (
                    self.userItem.get("doingutill") > int(time.time())) else False

    def addHungry(self, num):
        self.userItem['hungry'] += num
        self.user._set(hungry=self.userItem.get("hungry"))

    @RegCmd(
        name="我的背包",
        usage="我的背包",
        permission="anyone",
        description="我的背包",
        mode="我的世界"
    )
    def mybackpack(self):
        self.init()
        if not self.userItem:
            self.client.msg().raw("你还没出生呢，发送 出生")
            return
        message = ""
        for i in self.userItem.get("backpack"):
            if self.getBackpack(i):
                message += "\nface54{}: {}组余{}个".format(i,
                                                             int((self.getBackpack(i) - self.getBackpack(i) % 64) / 64),
                                                             self.getBackpack(i) % 64)
        self.client.msg().raw("[CQ:at,qq={0}] 您的背包：{1}".format(self.data.se.get('user_id'), message))

    @RegCmd(
        name="我的状态",
        usage="我的状态",
        permission="anyone",
        description="我的世界",
        mode="我的世界"
    )
    def mystatus(self):
        self.init()
        if not self.userItem:
            self.client.msg().raw("你还没出生呢，发送 出生")
            return
        self.client.msg().raw(
            "[CQ:at,qq={}] 您的状态：\nface54您的血量：{}\nface54您的饱食度：{}\nface54您的经验：{}".format(
                self.data.se.get("user_id"), self.userItem.get("life"), self.userItem.get("hungry"),
                self.userItem.get("xp")))

    @RegCmd(
        name="我在干什么",
        usage="我在干什么",
        permission="anyone",
        description="我在干什么",
        mode="我的世界"
    )
    def whatimdoing(self):
        self.init()
        if not self.userItem:
            self.client.msg().raw("你还没出生呢，发送 出生")
            return
        if ((not self.userItem.get("doing")) and (not self.userItem.get("doingutill"))) or (
                self.userItem.get("doingutill") < int(time.time())):
            self.client.msg().raw(
                "[CQ:at,qq={0}] 您的角色正在休息呢，赶紧找个事干吧！".format(self.data.se.get("user_id")))
        else:
            self.client.msg().raw(
                "[CQ:at,qq={0}] 您正在{1} 直到{2}".format(self.data.se.get("user_id"), self.userItem.get("doing"),
                                                          time.ctime(self.userItem.get("doingutill"))))

    @RegCmd(
        name="撸树",
        usage="撸树",
        permission="anyone",
        description="撸树",
        mode="我的世界"
    )
    def cuttree(self):
        if self.check():
            return
        nowtime = int(time.time())
        rand = random.randint(60, 600)
        randtime = nowtime + rand
        gettree = int(rand / 10)
        pig = random.randint(1, 10)
        hungry = int(rand / 60)
        self.addBackpack("猪肉", pig)
        self.addBackpack("原木", gettree)
        self.addEvent("撸树", randtime)
        self.addHungry(-1 * hungry)
        self.client.msg().raw(
            "[CQ:at,qq={0}] 开始撸树\nface54当前时间：{1}\nface54撸树时长：{2}秒\nface54获得树木：{3}块\nface54消耗{4}点饱食度\nface54顺便送走了{5}只老王，猪肉已加入背包\nface54获得{6}点经验\n请在{7}再回来领取树木吧！".format(
                self.data.se.get('user_id'), time.ctime(nowtime), rand, gettree, hungry, pig, self.randomXp(),
                time.ctime(randtime)))

    @RegCmd(
        name="出生",
        usage="出生",
        permission="anyone",
        description="出生",
        mode="我的世界"
    )
    def spawn(self):
        uid = self.data.se.get('user_id')
        self.init()
        if self.userItem:
            self.client.msg().raw("你还没死呢，无法重生！")
            return
        self.user = MCModel(
            qn=uid,
            name=self.data.se.get('sender').get('nickname'),
            life=20,
            hungry=20,
            backpack="{}",
            achievement="[]",
            xp=0,
            doing="",
            doingutill=0
        )
        self.client.msg().raw(
            "[CQ:at,qq={0}] 您已出生！\nface54初始生命值：20\nface54初始饱食度：20\n您接下来可以尝试撸树\n\n提示：MC功能机器人发送的所有时间都是UTC时间，与CST时间时差8小时！".format(
                uid))

    @RegCmd(
        name="挖矿",
        usage="挖矿",
        permission="anyone",
        description="挖矿",
        mode="我的世界"
    )
    def dig(self):
        uid = self.data.se.get("user_id")
        if self.check():
            return
        nowtime = int(time.time())
        rand = random.randint(60, 600)
        hungry = int(rand / 60)
        randtime = nowtime + rand
        stone = random.randint(0, rand)
        coal = random.randint(0, int(rand / 2))
        gold = random.randint(0, rand - coal)
        iron = random.randint(0, rand - coal - gold)
        diam = random.randint(0, rand - coal - gold - iron)
        message = ""

        if self.getBackpack("木镐") >= int(stone / 64) and self.getBackpack("木镐") != 0:
            self.addBackpack("圆石", stone)
            self.addBackpack("木镐", int(-1 * stone / 64))
            message += "\n    圆石：{} 消耗{}把木镐".format(stone, int(stone / 64))
        else:
            message += "\n    圆石：木镐不够"
        if self.getBackpack("石镐") >= int((iron + coal) / 64) and self.getBackpack("石镐") != 0:
            self.addBackpack("石镐", int(-1 * (iron + coal) / 64))
            self.addBackpack("铁锭", iron)
            self.addBackpack("煤炭", coal)
            message += "\n    煤炭：{}\n    铁锭：{} 消耗{}把石镐".format(coal, iron, int((iron + coal) / 64))
        else:
            message += "\n    煤炭：石镐不够\n    铁锭：石镐不够"
        if self.getBackpack("铁镐") >= int(gold / 64) and self.getBackpack("铁镐") != 0:
            self.addBackpack("铁镐", int(-1 * gold / 64))
            self.addBackpack("金锭", gold)
            message += "\n    金锭：{} 消耗{}把铁镐".format(gold, int(gold / 64))
        else:
            message += "\n    金锭：铁镐不够"
        if self.getBackpack("金镐") >= int(diam / 64) and self.getBackpack("金镐") != 0:
            self.addBackpack("金镐", int(-1 * diam / 64))
            self.addBackpack("钻石", diam)
            message += "\n    钻石：{} 消耗{}把金镐".format(diam, int(diam / 64))
        else:
            message += "\n    钻石：金镐不够"

        self.addHungry(hungry)
        self.addEvent("挖矿", randtime)
        self.client.msg().raw(
            "[CQ:at,qq={0}] 开始挖矿\nface54当前时间：{1}\nface54挖矿时长：{2}秒\nface54获得矿物：{3}\nface54消耗{4}点饱食度\nface54获得{5}点经验\n请在{6}再回来吧！".format(
                self.data.se.get('user_id'), time.ctime(nowtime), rand, message, hungry, self.randomXp(),
                time.ctime(randtime)))

    def check(self):
        self.init()
        if not self.userItem:
            self.client.msg().raw("你还没出生呢，发送 出生")
            return True
        if self.ifDoing():
            self.client.msg().raw("您先把手头的事干完把！")
            return True
        if self.userItem.get("hungry") <= 3:
            self.client.msg().raw("您太饿了，等明天恢复饱食度之后再进行操作吧！")
            return True
        return False

    @RegCmd(
        name="回饱食度",
        usage="回饱食度",
        permission="anyone",
        description="我的世界",
        mode="我的世界"
    )
    def eat(self):
        self.init()
        if not self.userItem:
            self.client.msg().raw("你还没出生呢，发送 出生")
            return
        message = "[CQ:at,qq={}] 已恢复饱食度：".format(self.data.se.get("user_id"))
        flag = False
        for i in self.eatList:
            if self.getBackpack(i) != 0:
                flag = True
            self.addHungry(self.getBackpack(i) * self.eatList.get(i))
            message += "\nface54{}恢复了{}点饱食度".format(i, self.getBackpack(i) * self.eatList.get(i))
            self.addBackpack(i, -1 * self.getBackpack(i))
        message += "\nface54当前饱食度：{}".format(self.userItem.get("hungry"))
        if Flag:
            message += "\nface54获得{}点经验".format(self.randomXp())
        self.client.msg().raw(message)

    @RegCmd(
        name="世界时间",
        usage="世界时间",
        permission="anyone",
        description="我的世界",
        mode="我的世界"
    )
    def worldtime(self):
        self.client.msg().raw("face54当前世界中的时间为：{}".format(time.ctime()))

    @RegCmd(
        name="打怪",
        usage="打怪",
        permission="anyone",
        description="我的世界",
        mode="我的世界"
    )
    def mobsComing(self):
        self.init()
        if self.userItem:
            if self.userItem.get("life") < 3:
                self.client.msg().raw(
                    "[CQ:at,qq={}] 遇到怪物，您的血量过低，被怪物撸死了！".format(self.data.se.get("user_id")))
                return self.die()
            ob = self.rclOb or self.commandListener.get()
            if ob == 404:
                spi = random.randint(0, int(self.userItem.get("life") / 2))
                ski = random.randint(0, int(self.userItem.get("life") / 2))
                bos = random.randint(0, int(self.userItem.get("life") / 2))
                cre = random.randint(0, int(self.userItem.get("life") / 2))
                message = "[CQ:at,qq={}] 遇到怪物\nface54蜘蛛：{}\nface54小白：{}\nface54僵尸：{}\nface54爬行者：{}\n请选择武器反击（发送 不使用 可以纯手撸怪）".format(
                    self.data.se.get("user_id"), spi, ski, bos, cre)
                self.client.msg().raw(message)
                self.commandListener.set("mc@mobsComing",
                                         args={"kill": spi + ski + bos + cre, "spi": spi, "ski": ski, "bos": bos,
                                               "cre": cre})
                return True

            args = ob.get('args')
            kill = args.get("kill")
            arrow = self.data.message
            if self.getBackpack(arrow) or arrow == "不使用":
                if self.userItem.get("life") * self.getKill(arrow) <= kill:
                    self.client.msg().raw("face54您的战斗力太低了，被怪物撸死了！")
                    self.die()
                else:
                    xp = random.randint(1, kill)
                    life = int(kill / 2 - self.getKill(arrow)) if arrow != "不使用" else int(kill / 2)
                    life = life if life >= 0 else 0
                    hungry = random.randint(0, life)
                    message = "face54怪物被击退\n减{}颗心\n减{}点饱食度\n获得{}点经验\n掉落物已加入背包".format(life,
                                                                                                                hungry,
                                                                                                                xp)
                    self.addHungry(-1 * hungry)
                    self.addBackpack("腐肉", args.get("bos"))
                    self.addBackpack("火药", args.get("cre"))
                    self.addBackpack("骨头", args.get("ski"))
                    self.addBackpack("线", args.get("spi"))
                    self.addXp(xp)
                    self.addLife(-1 * life)
                    if arrow != "不使用":
                        self.addBackpack(arrow, -1)
                        message += "\n消耗1个{}".format(arrow)
                    self.client.msg().raw(message)

                self.commandListener.remove()
            else:
                self.client.msg().raw("face54您没有这件武器，请重新选择（发送 不使用 可以纯手撸怪）")
        else:
            return False
        return True

    @RegCmd(
        name="合成 ",
        usage="合成 <物品> <数量，默认为1>",
        permission="anyone",
        description="我的世界",
        mode="我的世界"
    )
    def make(self):
        self.init()
        if not self.userItem:
            self.client.msg().raw("你还没出生呢，发送 出生")
            return
        thi = self.data.args[1]
        if self.data.args[-1] == thi:
            count = 1
        else:
            count = int(self.data.args[-1])
            if count < 0:
                count *= -1
            elif count == 0:
                return self.client.msg(
                    FaceStatement(32),
                    TextStatement("怎么能让我合成零个呢qwq")
                ).send()
        if self.makeTable.get(thi):
            message = "face54已合成！消耗："
            for i in self.makeTable.get(thi):
                if int(self.getBackpack(i.get("name"))) < int(i.get("count") * count):
                    return self.client.msg().raw("face54{}不够，需要{}个".format(i.get("name"), i.get("count") * count))
                self.addBackpack(i.get("name"), int(-1 * i.get("count") * count))
                message += "\n    {}: {}个".format(i.get("name"), i.get("count") * count)
            self.addBackpack(thi, count)
            message += "\nface54获得{}点经验".format(self.randomXp())
            self.client.msg().raw(message)
        else:
            self.client.msg().raw("face54合成表里没有该物品")

    @RegCmd(
        name="合成表",
        usage="合成表",
        permission="anyone",
        description="我的世界",
        mode="我的世界"
    )
    def listMakeTable(self):
        message = "face54合成表："
        for i in self.makeTable:
            message += "\nface54{}: ".format(i)
            for l in self.makeTable.get(i):
                message += "\n    {}: {}个".format(l.get("name"), l.get("count"))
        self.client.msg().raw(message)

    def save(self):
        self.init()
        if self.userItem and self.userItem.get("hungry") >= 10:
            life = random.randint(0, self.userItem.get("hungry")) / 2
            self.addLife(life)
            self.client.msg().raw(
                "[CQ:at,qq={}] 回血{}滴，现有{}滴".format(self.data.se.get("user_id"), life, self.userItem.get("life")))
        else:
            return False
        return True

    @RegCmd(
        name="丢弃 ",
        usage="丢弃 <物品> <数量，默认为全部>",
        permission="anyone",
        description="我的世界",
        mode="我的世界"
    )
    def throw(self):
        self.init()
        thi = self.data.args[1]
        if self.data.args[-1] == thi:
            count = self.getBackpack(thi)
        else:
            count = int(self.data.args[-1])
        if count < 0:
            count *= -1
        if count > self.getBackpack(thi):
            self.client.msg().raw("丢弃的物品数量多于背包数量，自动矫正")
            count = self.getBackpack(thi)
        self.addBackpack(thi, -1 * count)
        self.addXp(count)
        self.client.msg().raw("face54成功！同时获得经验{}点".format(count))

    @RegCmd(
        name="经验兑换血量",
        usage="经验兑换血量 <要兑换的经验的数量，默认为全部>",
        permission="anyone",
        description="我的世界",
        mode="我的世界"
    )
    def xpToLife(self):
        self.init()
        if not self.userItem:
            self.client.msg().raw("你还没出生呢，发送 出生")
            return
        if self.data.args[0] == self.data.args[-1]:
            xp = self.userItem.get('xp')
        else:
            xp = int(self.data.args[-1])
        if xp < 0:
            xp *= -1
        life = int(xp / 5)
        self.addXp(-1 * xp)
        self.addLife(life)
        self.client.msg().raw(
            "[CQ:at,qq={}] 已兑换！\nface54消耗{}点经验\nface54回了{}滴血".format(self.data.se.get("user_id"), xp, life))

    def giveout(self):
        to = self.data.args[1]
        thi = self.data.args[2]
        if self.data.args[2] == self.data.args[-1]:
            count = self.getBackpack(thi)
        else:
            count = self.data.args[-1]

    @RegCmd(
        name="血量兑换饱食度",
        usage="血量兑换饱食度 <要兑换的血量的数量>",
        permission="anyone",
        description="我的世界",
        mode="我的世界"
    )
    def lifeToHungry(self):
        self.init()
        if not self.userItem:
            self.client.msg().raw("你还没出生呢，发送 出生")
            return
        life = int(self.data.args[1])
        if life < 0:
            life *= -1
        hungry = int(life / 5)
        self.addHungry(hungry)
        self.addLife(-1 * life)
        self.client.msg().raw(
            "[CQ:at,qq={}] 已兑换！\nface54消耗{}滴血\nface54回了{}点饱食度".format(self.data.se.get("user_id"), life,
                                                                                   hungry))

    def pvp(self):
        pass

    @RegCmd(
        name="MCMessageListener",
        usage="MCMessageListener",
        permission="anyone",
        description="我的世界",
        mode="我的世界",
        type="message"
    )
    def messageListener(self):
        settings = self.data.groupSettings
        if not settings:
            return
        if settings._get("MC_random") == 0:
            return
        randnum = random.randint(0, int(settings._get("MC_random")))
        if randnum == 3:
            self.mobsComing()
        elif randnum == 4:
            self.save()
