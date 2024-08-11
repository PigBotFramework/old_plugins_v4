import math
import random
import re
import time
import traceback
from collections import namedtuple
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Dict, Optional, List, Tuple, Protocol
from urllib.request import urlopen

import imageio
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance
from PIL.Image import Image as IMG
from typing_extensions import Literal

from pbf.controller.Data import yamldata
from pbf.controller.PBF import PBF
from pbf.utils.CQCode import CQCode
from pbf.utils.RegCmd import RegCmd
from pbf.utils.pillow.build_image import BuildImage, Text2Image
from pbf.utils.pillow.fonts import Font
from pbf.utils.pillow.gradient import ColorStop, LinearGradient

_name = "表情包制作"
_version = "1.0.1"
_description = "表情包制作，轻松生成流行表情包，超过60多种！"
_author = "xzyStudio"
_cost = 0.00

TEXT_TOO_LONG = "文字太长了哦，改短点再试吧~"
NAME_TOO_LONG = "名字太长了哦，改短点再试吧~"
REQUIRE_NAME = "找不到名字，加上名字再试吧~"
REQUIRE_ARG = "该表情至少需要一个参数"
OVER_LENGTH_MSG = "太长啦！！！"


class Maker(Protocol):
    def __call__(self, img: BuildImage) -> BuildImage:
        ...


class GifMaker(Protocol):
    def __call__(self, i: int) -> Maker:
        ...


def get_avg_duration(image: IMG) -> float:
    if not getattr(image, "is_animated", False):
        return 0
    total_duration = 0
    for i in range(image.n_frames):
        image.seek(i)
        total_duration += image.info["duration"]
    return total_duration / image.n_frames


def split_gif(image: IMG) -> List[IMG]:
    frames: List[IMG] = []

    update_mode = "full"
    for i in range(image.n_frames):
        image.seek(i)
        if image.tile:  # type: ignore
            update_region = image.tile[0][1][2:]  # type: ignore
            if update_region != image.size:
                update_mode = "partial"
                break

    last_frame: Optional[IMG] = None
    for i in range(image.n_frames):
        image.seek(i)
        frame = image.copy()
        if update_mode == "partial" and last_frame:
            frame = last_frame.copy().paste(frame)
        frames.append(frame)
    image.seek(0)
    if image.info.__contains__("transparency"):
        frames[0].info["transparency"] = image.info["transparency"]
    return frames


class FrameAlignPolicy(Enum):
    """
    要叠加的gif长度大于基准gif时，是否延长基准gif长度以对齐两个gif
    """

    no_extend = 0
    """不延长"""
    extend_first = 1
    """延长第一帧"""
    extend_last = 2
    """延长最后一帧"""
    extend_loop = 3
    """以循环方式延长"""


def load_image(path):
    return BuildImage.open("./resources/images/" + path).convert("RGBA")


class petpet(PBF):
    def GetUserInfo(self, userid):
        return self.client.CallApi('get_stranger_info', {'user_id': userid}).get('data')

    def load_image(self, path):
        return load_image(path)

    def make_jpg_or_gif(self, img, func, gif_zoom=1, gif_max_frames=50) -> BytesIO:
        """
        制作静图或者动图
        :params
          * ``img``: 输入图片，如头像
          * ``func``: 图片处理函数，输入img，返回处理后的图片
          * ``gif_zoom``: gif 图片缩放比率，避免生成的 gif 太大
          * ``gif_max_frames``: gif 最大帧数，避免生成的 gif 太大
        """
        image = img.image
        if not getattr(image, "is_animated", False):
            return self.client.msg().raw('[CQ:image,file=https://pbfresources.xzynb.top/createimg/{0}]'.format(
                func(img.convert("RGBA")).save_jpg()))
        else:
            index = range(image.n_frames)
            ratio = image.n_frames / gif_max_frames
            duration = image.info["duration"] / 1000
            if ratio > 1:
                index = (int(i * ratio) for i in range(gif_max_frames))
                duration *= ratio

            frames = []
            for i in index:
                image.seek(i)
                new_img = func(BuildImage(image).convert("RGBA"))
                frames.append(
                    new_img.resize(
                        (int(new_img.width * gif_zoom), int(new_img.height * gif_zoom))
                    ).image
                )
            return self.save_gif(frames, duration)

    def save_gif(self, frames: List[IMG], duration: float):
        filename = '{0}.gif'.format(time.time())
        output = './resources/createimg/{0}'.format(filename)
        imageio.mimsave(output, frames, format="gif", duration=duration)
        self.client.msg().raw('[CQ:image,file=https://pbfresources.xzynb.top/createimg/{0}]'.format(filename))
        return output

    def GetImage(self, userid=None):
        if not userid:
            userid = self.data.message
            if ' ' in userid:
                userid = userid.split(' ')[0]
            if 'at' in userid:
                userid = CQCode(userid).get('qq')[0]

            if userid == str(self.data.botSettings._get("owner")) or userid == str(
                    self.data.botSettings._get("myselfqn")) or userid == str(yamldata.get("chat").get("owner")):
                userid = self.data.se.get('user_id')

        url = "http://q2.qlogo.cn/headimg_dl?dst_uin={0}&spec=100".format(userid)
        try:
            image_bytes = urlopen(url).read()
            # internal data file
            data_stream = BytesIO(image_bytes)
            # open as a PIL image object
            # 以一个PIL图像对象打开
            return BuildImage.open(data_stream)
        except Exception as e:
            self.client.msg().raw("获取用户头像失败，请重试")

    def save_and_send(self, frame):
        self.client.msg().raw(
            '[CQ:image,file=https://pbfresources.xzynb.top/createimg/{0}]'.format(frame.save_jpg()))

    def make_gif_or_combined_gif(
            self,
            img: BuildImage,
            maker: GifMaker,
            frame_num: int,
            duration: float,
            frame_align: FrameAlignPolicy = FrameAlignPolicy.no_extend,
            input_based: bool = False,
            keep_transparency: bool = False,
    ) -> BytesIO:
        """
        使用静图或动图制作gif
        :params
          * ``img``: 输入图片，如头像
          * ``maker``: 图片处理函数生成，传入第几帧，返回对应的图片处理函数
          * ``frame_num``: 目标gif的帧数
          * ``duration``: 相邻帧之间的时间间隔，单位为秒
          * ``frame_align``: 要叠加的gif长度大于基准gif时，gif长度对齐方式
          * ``input_based``: 是否以输入gif为基准合成gif，默认为`False`，即以目标gif为基准
          * ``keep_transparency``: 传入gif时，是否保留该gif的透明度
        """
        image = img.image
        if not getattr(image, "is_animated", False):
            return self.save_gif([maker(i)(img).image for i in range(frame_num)], duration)

        frame_num_in = image.n_frames
        duration_in = get_avg_duration(image) / 1000
        total_duration_in = frame_num_in * duration_in
        total_duration = frame_num * duration

        if input_based:
            frame_num_base = frame_num_in
            frame_num_fit = frame_num
            duration_base = duration_in
            duration_fit = duration
            total_duration_base = total_duration_in
            total_duration_fit = total_duration
        else:
            frame_num_base = frame_num
            frame_num_fit = frame_num_in
            duration_base = duration
            duration_fit = duration_in
            total_duration_base = total_duration
            total_duration_fit = total_duration_in

        frame_idxs: List[int] = list(range(frame_num_base))
        diff_duration = total_duration_fit - total_duration_base
        diff_num = int(diff_duration / duration_base)

        if diff_duration >= duration_base:
            if frame_align == FrameAlignPolicy.extend_first:
                frame_idxs = [0] * diff_num + frame_idxs

            elif frame_align == FrameAlignPolicy.extend_last:
                frame_idxs += [frame_num_base - 1] * diff_num

            elif frame_align == FrameAlignPolicy.extend_loop:
                frame_num_total = frame_num_base
                # 重复基准gif，直到两个gif总时长之差在1个间隔以内，或总帧数超出最大帧数
                while (
                        frame_num_total + frame_num_base <= 100
                ):
                    frame_num_total += frame_num_base
                    frame_idxs += list(range(frame_num_base))
                    multiple = round(frame_num_total * duration_base / total_duration_fit)
                    if (
                            math.fabs(
                                total_duration_fit * multiple - frame_num_total * duration_base
                            )
                            <= duration_base
                    ):
                        break

        frames: List[IMG] = []
        frame_idx_fit = 0
        time_start = 0
        for i, idx in enumerate(frame_idxs):
            while frame_idx_fit < frame_num_fit:
                if (
                        frame_idx_fit * duration_fit
                        <= i * duration_base - time_start
                        < (frame_idx_fit + 1) * duration_fit
                ):
                    if input_based:
                        idx_in = idx
                        idx_maker = frame_idx_fit
                    else:
                        idx_in = frame_idx_fit
                        idx_maker = idx

                    func = maker(idx_maker)
                    image.seek(idx_in)
                    frames.append(func(BuildImage(image.copy())).image)
                    break
                else:
                    frame_idx_fit += 1
                    if frame_idx_fit >= frame_num_fit:
                        frame_idx_fit = 0
                        time_start += total_duration_fit

        if keep_transparency:
            image.seek(0)
            if image.info.__contains__("transparency"):
                frames[0].info["transparency"] = image.info["transparency"]

        return self.save_gif(frames, duration)

    def GetArgs(self):
        return " ".join(self.data.args[2:len(self.data.args)]).strip()

    @RegCmd(
        name="偷学 ",
        usage="偷学 <QQ号或@对方>[ <附加内容>]",
        permission="anyone",
        description="偷学",
        mode="表  情  包"
    )
    def learn(self):
        arg = self.GetArgs()
        img = self.GetImage()
        text = arg or "偷学群友数理基础"
        frame = load_image("learn/0.png")
        try:
            frame.draw_text(
                (100, 1360, frame.width - 100, 1730),
                text,
                max_fontsize=350,
                min_fontsize=200,
                weight="bold",
            )
        except ValueError:
            return TEXT_TOO_LONG

        def make(img: BuildImage) -> BuildImage:
            return frame.copy().paste(
                img.resize((1751, 1347), keep_ratio=True), (1440, 0), alpha=True
            )

        self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="坐得住 ",
        usage="坐得住 <QQ号或@对方>",
        permission="anyone",
        description="坐得住",
        mode="表  情  包"
    )
    def sit_still(self):
        img = self.GetImage()
        userid = self.data.message
        if 'at' in userid:
            userid = CQCode(userid).get('qq')[0]

        name = self.GetUserInfo(userid).get('nickname')
        frame = load_image("sit_still/0.png")
        try:
            frame.draw_text(
                (100, 170, 600, 330),
                name,
                valign="bottom",
                max_fontsize=75,
                min_fontsize=30,
            )
        except ValueError:
            return NAME_TOO_LONG
        img = img.convert("RGBA").circle().resize((150, 150)).rotate(-10, expand=True)
        frame.paste(img, (268, 344), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="踢球 ",
        usage="踢球 <QQ号或@对方>",
        permission="anyone",
        description="踢球",
        mode="表  情  包"
    )
    def kick_ball(self):
        img = self.GetImage()
        img = img.convert("RGBA").square().resize((78, 78))
        # fmt: off
        locs = [
            (57, 136), (56, 117), (55, 99), (52, 113), (50, 126),
            (48, 139), (47, 112), (47, 85), (47, 57), (48, 97),
            (50, 136), (51, 176), (52, 169), (55, 181), (58, 153)
        ]
        # fmt: on
        frames: List[IMG] = []
        for i in range(15):
            frame = load_image(f"kick_ball/{i}.png")
            frame.paste(img.rotate(-24 * i), locs[i], below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.1)

    @RegCmd(
        name="波奇手稿 ",
        usage="波奇手稿 <QQ号或@对方>",
        permission="anyone",
        description="波奇手稿",
        mode="表  情  包"
    )
    def bocchi_draft(self):
        img = self.GetImage()
        img = img.convert("RGBA").resize((350, 400), keep_ratio=True)
        params = [
            (((54, 62), (353, 1), (379, 382), (1, 399)), (146, 173)),
            (((54, 61), (349, 1), (379, 381), (1, 398)), (146, 174)),
            (((54, 61), (349, 1), (379, 381), (1, 398)), (152, 174)),
            (((54, 61), (335, 1), (379, 381), (1, 398)), (158, 167)),
            (((54, 61), (335, 1), (370, 381), (1, 398)), (157, 149)),
            (((41, 59), (321, 1), (357, 379), (1, 396)), (167, 108)),
            (((41, 57), (315, 1), (357, 377), (1, 394)), (173, 69)),
            (((41, 56), (309, 1), (353, 380), (1, 393)), (175, 43)),
            (((41, 56), (314, 1), (353, 380), (1, 393)), (174, 30)),
            (((41, 50), (312, 1), (348, 367), (1, 387)), (171, 18)),
            (((35, 50), (306, 1), (342, 367), (1, 386)), (178, 14)),
        ]
        # fmt: off
        idx = [
            0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10,
        ]
        # fmt: on
        frames: List[IMG] = []
        for i in range(23):
            frame = load_image(f"bocchi_draft/{i}.png")
            points, pos = params[idx[i]]
            frame.paste(img.perspective(points), pos, below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.08)

    @RegCmd(
        name="砸 ",
        usage="砸 <QQ号或@对方>",
        permission="anyone",
        description="砸",
        mode="表  情  包"
    )
    def smash(self):
        img = self.GetImage()
        frame = load_image("smash/0.png")

        def make(img: BuildImage) -> BuildImage:
            points = ((1, 237), (826, 1), (832, 508), (160, 732))
            screen = img.resize((800, 500), keep_ratio=True).perspective(points)
            return frame.copy().paste(screen, (-136, -81), below=True)

        self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="木鱼 ",
        usage="木鱼 <QQ号或@对方>",
        permission="anyone",
        description="木鱼",
        mode="表  情  包"
    )
    def wooden_fish(self):
        img = self.GetImage()
        img = img.convert("RGBA").resize((85, 85))
        frames = [
            load_image(f"wooden_fish/{i}.png").paste(img, (116, 153), below=True).image
            for i in range(66)
        ]
        self.save_gif(frames, 0.1)

    @RegCmd(
        name="凯露指 ",
        usage="凯露指 <QQ号或@对方>",
        permission="anyone",
        description="凯露指",
        mode="表  情  包"
    )
    def karyl_point(self):
        img = self.GetImage()
        img = img.convert("RGBA").rotate(7.5, expand=True).resize((225, 225))
        frame = load_image("karyl_point/0.png")
        frame.paste(img, (87, 790), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="卡比锤 ",
        usage="卡比锤 <QQ号或@对方>",
        permission="anyone",
        description="卡比锤",
        mode="表  情  包"
    )
    def kirby_hammer(self):
        img = self.GetImage()
        # fmt: off
        positions = [
            (318, 163), (319, 173), (320, 183), (317, 193), (312, 199),
            (297, 212), (289, 218), (280, 224), (278, 223), (278, 220),
            (280, 215), (280, 213), (280, 210), (280, 206), (280, 201),
            (280, 192), (280, 188), (280, 184), (280, 179)
        ]

        # fmt: on
        def maker(i: int) -> Maker:
            def make(img: BuildImage) -> BuildImage:
                img = img.convert("RGBA")
                img = img.circle()
                img = img.resize_height(80)
                if img.width < 80:
                    img = img.resize((80, 80), keep_ratio=True)
                frame = load_image(f"kirby_hammer/{i}.png")
                if i <= 18:
                    x, y = positions[i]
                    x = x + 40 - img.width // 2
                    frame.paste(img, (x, y), alpha=True)
                elif i <= 39:
                    x, y = positions[18]
                    x = x + 40 - img.width // 2
                    frame.paste(img, (x, y), alpha=True)
                return frame

            return make

        self.make_gif_or_combined_gif(img, maker, 62, 0.05, FrameAlignPolicy.extend_loop)

    @RegCmd(
        name="诈尸 ",
        usage="诈尸 <QQ号或@对方>",
        permission="anyone",
        description="诈尸",
        mode="表  情  包"
    )
    def rise_dead(self):
        img = self.GetImage()
        locs = [
            ((81, 55), ((0, 2), (101, 0), (103, 105), (1, 105))),
            ((74, 49), ((0, 3), (104, 0), (106, 108), (1, 108))),
            ((-66, 36), ((0, 0), (182, 5), (184, 194), (1, 185))),
            ((-231, 55), ((0, 0), (259, 4), (276, 281), (13, 278))),
        ]
        img = img.convert("RGBA").square().resize((150, 150))
        imgs = [img.perspective(points) for _, points in locs]
        frames: List[IMG] = []
        for i in range(34):
            frame = load_image(f"rise_dead/{i}.png")
            if i <= 28:
                idx = 0 if i <= 25 else i - 25
                x, y = locs[idx][0]
                if i % 2 == 1:
                    x += 1
                    y -= 1
                frame.paste(imgs[idx], (x, y), below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.15)

    @RegCmd(
        name="波纹 ",
        usage="波纹 <QQ号或@对方>",
        permission="anyone",
        description="波纹",
        mode="表  情  包"
    )
    def wave(self):
        img = self.GetImage()
        img_w = min(max(img.width, 360), 720)
        period = img_w / 6
        amp = img_w / 60
        frame_num = 8
        phase = 0
        sin = lambda x: amp * math.sin(2 * math.pi / period * (x + phase)) / 2

        def maker(i: int) -> Maker:
            def make(img: BuildImage) -> BuildImage:
                img = img.resize_width(img_w)
                img_h = img.height
                frame = img.copy()
                for i in range(img_w):
                    for j in range(img_h):
                        dx = int(sin(i) * (img_h - j) / img_h)
                        dy = int(sin(j) * j / img_h)
                        if 0 <= i + dx < img_w and 0 <= j + dy < img_h:
                            frame.image.putpixel(
                                (i, j), img.image.getpixel((i + dx, j + dy))
                            )

                frame = frame.resize_canvas((int(img_w - amp), int(img_h - amp)))
                nonlocal phase
                phase += period / frame_num
                return frame

            return make

        self.make_gif_or_combined_gif(
            img, maker, frame_num, 0.01, FrameAlignPolicy.extend_loop
        )

    @RegCmd(
        name="一起 ",
        usage="一起 <QQ号或@对方>",
        permission="anyone",
        description="一起",
        mode="表  情  包"
    )
    def together(self):
        img = self.GetImage()
        userid = self.data.message
        if 'at' in userid:
            userid = CQCode(userid).get("qq")[0]

        username = self.GetUserInfo(userid).get('nickname')
        frame = load_image("together/0.png")
        frame.paste(img.convert("RGBA").resize((63, 63)), (132, 36))
        text = f"一起玩{username}吧！"
        try:
            frame.draw_text(
                (10, 140, 190, 190),
                text,
                weight="bold",
                max_fontsize=50,
                min_fontsize=10,
                allow_wrap=True,
            )
        except ValueError:
            return TEXT_TOO_LONG
        self.save_and_send(frame)

    @RegCmd(
        name="不文明 ",
        usage="不文明 <QQ号或@对方>[ <附加内容>]",
        permission="anyone",
        description="不文明",
        mode="表  情  包"
    )
    def incivilization(self):
        img = self.GetImage()
        arg = self.GetArgs()
        frame = load_image("incivilization/0.png")
        points = ((0, 20), (154, 0), (164, 153), (22, 180))
        img = img.convert("RGBA").circle().resize((150, 150)).perspective(points)
        image = ImageEnhance.Brightness(img.image).enhance(0.8)
        frame.paste(image, (137, 151), alpha=True)
        text = arg or "你刚才说的话不是很礼貌！"
        try:
            frame.draw_text(
                (57, 42, 528, 117),
                text,
                weight="bold",
                max_fontsize=50,
                min_fontsize=20,
                allow_wrap=True,
            )
        except ValueError:
            return TEXT_TOO_LONG
        self.save_and_send(frame)

    @RegCmd(
        name="急急国王 ",
        usage="急急国王 <QQ号或@对方>[ <附加内容>]",
        permission="anyone",
        description="急急国王",
        mode="表  情  包"
    )
    def jiji_king(self):
        args = self.GetArgs().split()
        user_imgs: List[BuildImage] = []
        user_imgs.append(self.GetImage())

        block_num = 5
        if len(user_imgs) >= 7 or len(args) >= 7:
            block_num = max(len(user_imgs), len(args)) - 1

        chars = ["急"]
        text = "我是急急国王"
        if len(args) == 1:
            if len(user_imgs) == 1:
                chars = [args[0]] * block_num
                text = f"我是{args[0] * 2}国王"
            else:
                text = args[0]
        elif len(args) == 2:
            chars = [args[0]] * block_num
            text = args[1]
        elif args:
            chars = sum(
                [[arg] * math.ceil(block_num / len(args[:-1])) for arg in args[:-1]], []
            )
            text = args[-1]

        frame = BuildImage.new("RGBA", (10 + 100 * block_num, 400), "white")
        king = load_image("jiji_king/0.png")
        king.paste(
            user_imgs[0].convert("RGBA").square().resize((125, 125)), (237, 5), alpha=True
        )
        frame.paste(king, ((frame.width - king.width) // 2, 0))

        if len(user_imgs) > 1:
            imgs = user_imgs[1:]
            imgs = [img.convert("RGBA").square().resize((90, 90)) for img in imgs]
        else:
            imgs = []
            for char in chars:
                block = BuildImage.new("RGBA", (90, 90), "black")
                try:
                    block.draw_text(
                        (0, 0, 90, 90),
                        char,
                        lines_align="center",
                        weight="bold",
                        max_fontsize=60,
                        min_fontsize=30,
                        fill="white",
                    )
                except ValueError:
                    return TEXT_TOO_LONG
                imgs.append(block)

        imgs = sum([[img] * math.ceil(block_num / len(imgs)) for img in imgs], [])
        for i in range(block_num):
            frame.paste(imgs[i], (10 + 100 * i, 200))

        try:
            frame.draw_text(
                (10, 300, frame.width - 10, 390),
                text,
                lines_align="center",
                weight="bold",
                max_fontsize=100,
                min_fontsize=30,
            )
        except ValueError:
            return TEXT_TOO_LONG

        self.save_and_send(frame)

    @RegCmd(
        name="舰长 ",
        usage="舰长 <QQ号或@对方>",
        permission="anyone",
        description="舰长",
        mode="表  情  包"
    )
    def captain(self):
        sender_img = self.GetImage(self.data.se.get("user_id"))
        user_img = self.GetImage()
        imgs: List[BuildImage] = []
        imgs.append(sender_img)
        imgs.append(user_img)
        imgs.append(user_img)

        bg0 = load_image("captain/0.png")
        bg1 = load_image("captain/1.png")
        bg2 = load_image("captain/2.png")

        frame = BuildImage.new("RGBA", (640, 440 * len(imgs)), "white")
        for i in range(len(imgs)):
            bg = bg0 if i < len(imgs) - 2 else bg1 if i == len(imgs) - 2 else bg2
            imgs[i] = imgs[i].convert("RGBA").square().resize((250, 250))
            bg = bg.copy().paste(imgs[i], (350, 85))
            frame.paste(bg, (0, 440 * i))

        self.save_and_send(frame)

    @RegCmd(
        name="看图标 ",
        usage="看图标 <QQ号或@对方>",
        permission="anyone",
        description="看图标",
        mode="表  情  包"
    )
    def look_this_icon(self):
        img = self.GetImage()
        text = self.GetArgs() or "朋友\n先看看这个图标再说话"
        frame = load_image("look_this_icon/nmsl.png")
        try:
            frame.draw_text(
                (0, 933, 1170, 1143),
                text,
                lines_align="center",
                weight="bold",
                max_fontsize=100,
                min_fontsize=50,
            )
        except ValueError:
            return TEXT_TOO_LONG

        def make(img: BuildImage) -> BuildImage:
            img = img.convert("RGBA").resize((515, 515), keep_ratio=True)
            return frame.copy().paste(img, (599, 403), below=True)

        self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="看扁 ",
        usage="看扁 <QQ号或@对方>[ <附加内容，文字内容和拉扁比例>]",
        permission="anyone",
        description="看扁",
        mode="表  情  包"
    )
    def look_flat(self):
        img = self.GetImage()
        args = self.GetArgs().split()
        ratio = 2
        text = "可恶...被人看扁了"
        for arg in args:
            if arg.isdigit():
                ratio = int(arg)
                if ratio < 2 or ratio > 10:
                    ratio = 2
            elif arg:
                text = arg

        img_w = 500
        text_h = 80
        text_frame = BuildImage.new("RGBA", (img_w, text_h), "white")
        try:
            text_frame.draw_text(
                (10, 0, img_w - 10, text_h),
                text,
                max_fontsize=55,
                min_fontsize=30,
                weight="bold",
            )
        except ValueError:
            return TEXT_TOO_LONG

        def make(img: BuildImage) -> BuildImage:
            img = img.convert("RGBA").resize_width(img_w)
            img = img.resize((img_w, img.height // ratio))
            img_h = img.height
            frame = BuildImage.new("RGBA", (img_w, img_h + text_h), "white")
            return frame.paste(img, alpha=True).paste(text_frame, (0, img_h), alpha=True)

        self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="抱紧 ",
        usage="抱紧 <QQ号或@对方>",
        permission="anyone",
        description="抱紧",
        mode="表  情  包"
    )
    def hold_tight(self):
        img = self.GetImage()
        img = img.convert("RGBA").resize((159, 171), keep_ratio=True)
        frame = load_image("hold_tight/0.png")
        frame.paste(img, (113, 205), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="无响应 ",
        usage="无响应 <QQ号或@对方>",
        permission="anyone",
        description="无响应",
        mode="表  情  包"
    )
    def no_response(self):
        img = self.GetImage()
        img = img.convert("RGBA").resize((1050, 783), keep_ratio=True)
        frame = load_image("no_response/0.png")
        frame.paste(img, (0, 581), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="唐可可举牌 ",
        usage="唐可可举牌 <QQ号或@对方>",
        permission="anyone",
        description="唐可可举牌",
        mode="表  情  包"
    )
    def tankuku_holdsign(self):
        img = self.GetImage()
        img = img.convert("RGBA").resize((300, 230), keep_ratio=True)
        params = (
            (((0, 46), (320, 0), (350, 214), (38, 260)), (68, 91)),
            (((18, 0), (328, 28), (298, 227), (0, 197)), (184, 77)),
            (((15, 0), (294, 28), (278, 216), (0, 188)), (194, 65)),
            (((14, 0), (279, 27), (262, 205), (0, 178)), (203, 55)),
            (((14, 0), (270, 25), (252, 195), (0, 170)), (209, 49)),
            (((15, 0), (260, 25), (242, 186), (0, 164)), (215, 41)),
            (((10, 0), (245, 21), (230, 180), (0, 157)), (223, 35)),
            (((13, 0), (230, 21), (218, 168), (0, 147)), (231, 25)),
            (((13, 0), (220, 23), (210, 167), (0, 140)), (238, 21)),
            (((27, 0), (226, 46), (196, 182), (0, 135)), (254, 13)),
            (((27, 0), (226, 46), (196, 182), (0, 135)), (254, 13)),
            (((27, 0), (226, 46), (196, 182), (0, 135)), (254, 13)),
            (((0, 35), (200, 0), (224, 133), (25, 169)), (175, 9)),
            (((0, 35), (200, 0), (224, 133), (25, 169)), (195, 17)),
            (((0, 35), (200, 0), (224, 133), (25, 169)), (195, 17)),
        )
        frames: List[IMG] = []
        for i in range(15):
            points, pos = params[i]
            frame = load_image(f"tankuku_holdsign/{i}.png")
            frame.paste(img.perspective(points), pos, below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.2)

    @RegCmd(
        name="抱大腿 ",
        usage="抱大腿 <QQ号或@对方>",
        permission="anyone",
        description="抱大腿",
        mode="表  情  包"
    )
    def hug_leg(self):
        img = self.GetImage()
        img = img.convert("RGBA").square()
        locs = [
            (50, 73, 68, 92),
            (58, 60, 62, 95),
            (65, 10, 67, 118),
            (61, 20, 77, 97),
            (55, 44, 65, 106),
            (66, 85, 60, 98),
        ]
        frames: List[IMG] = []
        for i in range(6):
            frame = load_image(f"hug_leg/{i}.png")
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.06)

    @RegCmd(
        name="击剑 ",
        usage="击剑 <QQ号或@对方>",
        permission="anyone",
        description="击剑",
        mode="表  情  包"
    )
    def fencing(self):
        self_img = self.GetImage(self.data.se.get("user_id"))
        user_img = self.GetImage()
        self_head = self_img.convert("RGBA").circle().resize((27, 27))
        user_head = user_img.convert("RGBA").circle().resize((27, 27))
        # fmt: off
        user_locs = [
            (57, 4), (55, 5), (58, 7), (57, 5), (53, 8), (54, 9),
            (64, 5), (66, 8), (70, 9), (73, 8), (81, 10), (77, 10),
            (72, 4), (79, 8), (50, 8), (60, 7), (67, 6), (60, 6), (50, 9)
        ]
        self_locs = [
            (10, 6), (3, 6), (32, 7), (22, 7), (13, 4), (21, 6),
            (30, 6), (22, 2), (22, 3), (26, 8), (23, 8), (27, 10),
            (30, 9), (17, 6), (12, 8), (11, 7), (8, 6), (-2, 10), (4, 9)
        ]
        # fmt: on
        frames: List[IMG] = []
        for i in range(19):
            frame = load_image(f"fencing/{i}.png")
            frame.paste(user_head, user_locs[i], alpha=True)
            frame.paste(self_head, self_locs[i], alpha=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.05)

    @RegCmd(
        name="打穿 ",
        usage="打穿 <QQ号或@对方>",
        permission="anyone",
        description="打穿",
        mode="表  情  包"
    )
    def hit_screen(self):
        img = self.GetImage()
        params = (
            (((1, 10), (138, 1), (140, 119), (7, 154)), (32, 37)),
            (((1, 10), (138, 1), (140, 121), (7, 154)), (32, 37)),
            (((1, 10), (138, 1), (139, 125), (10, 159)), (32, 37)),
            (((1, 12), (136, 1), (137, 125), (8, 159)), (34, 37)),
            (((1, 9), (137, 1), (139, 122), (9, 154)), (35, 41)),
            (((1, 8), (144, 1), (144, 123), (12, 155)), (30, 45)),
            (((1, 8), (140, 1), (141, 121), (10, 155)), (29, 49)),
            (((1, 9), (140, 1), (139, 118), (10, 153)), (27, 53)),
            (((1, 7), (144, 1), (145, 117), (13, 153)), (19, 57)),
            (((1, 7), (144, 1), (143, 116), (13, 153)), (19, 57)),
            (((1, 8), (139, 1), (141, 119), (12, 154)), (19, 55)),
            (((1, 13), (140, 1), (143, 117), (12, 156)), (16, 57)),
            (((1, 10), (138, 1), (142, 117), (11, 149)), (14, 61)),
            (((1, 10), (141, 1), (148, 125), (13, 153)), (11, 57)),
            (((1, 12), (141, 1), (147, 130), (16, 150)), (11, 60)),
            (((1, 15), (165, 1), (175, 135), (1, 171)), (-6, 46)),
        )

        def maker(i: int) -> Maker:
            def make(img: BuildImage) -> BuildImage:
                img = img.resize((140, 120), keep_ratio=True)
                frame = load_image(f"hit_screen/{i}.png")
                if 6 <= i < 22:
                    points, pos = params[i - 6]
                    frame.paste(img.perspective(points), pos, below=True)
                return frame

            return make

        self.make_gif_or_combined_gif(img, maker, 29, 0.2, FrameAlignPolicy.extend_first)

    @RegCmd(
        name="迷惑 ",
        usage="迷惑 <QQ号或@对方>",
        permission="anyone",
        description="迷惑",
        mode="表  情  包"
    )
    def confuse(self):
        img = self.GetImage()
        img_w = min(img.width, 500)

        def maker(i: int) -> Maker:
            def make(img: BuildImage) -> BuildImage:
                img = img.resize_width(img_w)
                frame = load_image(f"confuse/{i}.png").resize(img.size, keep_ratio=True)
                bg = BuildImage.new("RGB", img.size, "white")
                bg.paste(img, alpha=True).paste(frame, alpha=True)
                return bg

            return make

        self.make_gif_or_combined_gif(
            img, maker, 100, 0.02, FrameAlignPolicy.extend_loop, input_based=True
        )

    @RegCmd(
        name="遇到困难请拨打 ",
        usage="遇到困难请拨打 <QQ号或@对方>",
        permission="anyone",
        description="遇到困难请拨打",
        mode="表  情  包"
    )
    def call_110(self):
        img1 = self.GetImage(self.data.se.get("user_id"))
        img0 = self.GetImage()
        img1 = img1.convert("RGBA").square().resize((250, 250))
        img0 = img0.convert("RGBA").square().resize((250, 250))

        frame = BuildImage.new("RGB", (900, 500), "white")
        frame.draw_text((0, 0, 900, 200), "遇到困难请拨打", max_fontsize=100)
        frame.paste(img1, (50, 200), alpha=True)
        frame.paste(img1, (325, 200), alpha=True)
        frame.paste(img0, (600, 200), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="看书 ",
        usage="看书 <QQ号或@对方>[ <附加内容>]",
        permission="anyone",
        description="看书",
        mode="表  情  包"
    )
    def read_book(self):
        img = self.GetImage()
        arg = self.GetArgs()
        frame = load_image("read_book/0.png")
        points = ((0, 108), (1092, 0), (1023, 1134), (29, 1134))
        img = img.convert("RGBA").resize((1000, 1100), keep_ratio=True, direction="north")
        cover = img.perspective(points)
        frame.paste(cover, (1138, 1172), below=True)
        if arg:
            chars = list(" ".join(arg.splitlines()))
            pieces: List[BuildImage] = []
            for char in chars:
                piece = BuildImage(
                    Text2Image.from_text(char, 200, fill="white", weight="bold").to_image()
                )
                if re.fullmatch(r"[a-zA-Z0-9\s]", char):
                    piece = piece.rotate(-90, expand=True)
                else:
                    piece = piece.resize_canvas((piece.width, piece.height - 40), "south")
                pieces.append(piece)
            w = max((piece.width for piece in pieces))
            h = sum((piece.height for piece in pieces))
            if w > 265 or h > 3000:
                return TEXT_TOO_LONG
            text_img = BuildImage.new("RGBA", (w, h))
            h = 0
            for piece in pieces:
                text_img.paste(piece, ((w - piece.width) // 2, h), alpha=True)
                h += piece.height
            if h > 780:
                ratio = 780 / h
                text_img = text_img.resize((int(w * ratio), int(h * ratio)))
            text_img = text_img.rotate(3, expand=True)
            w, h = text_img.size
            frame.paste(text_img, (870 + (240 - w) // 2, 1500 + (780 - h) // 2), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="高血压 ",
        usage="高血压 <QQ号或@对方>",
        permission="anyone",
        description="高血压",
        mode="表  情  包"
    )
    def blood_pressure(self):
        img = self.GetImage()
        frame = load_image("blood_pressure/0.png")

        def make(img: BuildImage) -> BuildImage:
            return frame.copy().paste(
                img.resize((414, 450), keep_ratio=True), (16, 17), below=True
            )

        self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="手枪 ",
        usage="手枪 <QQ号或@对方>",
        permission="anyone",
        description="手枪",
        mode="表  情  包"
    )
    def gun(self):
        img = self.GetImage()
        frame = load_image("gun/0.png")
        frame.paste(img.convert("RGBA").resize((500, 500), keep_ratio=True), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="上瘾 ",
        usage="上瘾 <QQ号或@对方>",
        permission="anyone",
        description="上瘾",
        mode="表  情  包"
    )
    def addition(self):
        frame = load_image("addiction/0.png")
        img = self.GetImage()
        arg = self.GetArgs()
        if arg:
            expand_frame = BuildImage.new("RGBA", (246, 286), "white")
            expand_frame.paste(frame)
            try:
                expand_frame.draw_text(
                    (10, 246, 236, 286),
                    arg,
                    max_fontsize=45,
                    lines_align="center",
                )
            except ValueError:
                return TEXT_TOO_LONG
            frame = expand_frame

        def make(img: BuildImage) -> BuildImage:
            return frame.copy().paste(img.resize((70, 70), keep_ratio=True), (0, 0))

        self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="敲黑板 ",
        usage="敲黑板 <QQ号或@对方> <附加内容>",
        permission="anyone",
        description="敲黑板",
        mode="表  情  包"
    )
    def teach(self):
        img = self.GetImage()
        arg = self.GetArgs()
        frame = load_image("teach/0.png").resize_width(960).convert("RGBA")
        try:
            frame.draw_text(
                (10, frame.height - 80, frame.width - 10, frame.height - 5),
                arg,
                max_fontsize=50,
                fill="white",
                stroke_fill="black",
                stroke_ratio=0.06,
            )
        except ValueError:
            return TEXT_TOO_LONG

        def make(img: BuildImage) -> BuildImage:
            return frame.copy().paste(
                img.resize((550, 395), keep_ratio=True), (313, 60), below=True
            )

        self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="胡桃放大 ",
        usage="胡桃放大 <QQ号或@对方>",
        permission="anyone",
        description="胡桃放大",
        mode="表  情  包"
    )
    def walnut_zoom(self):
        img = self.GetImage()
        # fmt: off
        locs = (
            (-222, 30, 695, 430), (-212, 30, 695, 430), (0, 30, 695, 430), (41, 26, 695, 430),
            (-100, -67, 922, 570), (-172, -113, 1059, 655), (-273, -192, 1217, 753)
        )
        seq = [0, 0, 0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 5, 6, 6, 6, 6]

        # fmt: on

        def maker(i: int) -> Maker:
            def make(img: BuildImage) -> BuildImage:
                frame = load_image(f"walnut_zoom/{i}.png")
                x, y, w, h = locs[seq[i]]
                img = img.resize((w, h), keep_ratio=True).rotate(4.2, expand=True)
                frame.paste(img, (x, y), below=True)
                return frame

            return make

        self.make_gif_or_combined_gif(img, maker, 24, 0.2, FrameAlignPolicy.extend_last)

    @RegCmd(
        name="胡桃平板 ",
        usage="胡桃平板 <QQ号或@对方>",
        permission="anyone",
        description="胡桃平板",
        mode="表  情  包"
    )
    def walnutpad(self):
        img = self.GetImage()
        frame = load_image("walnutpad/0.png")

        def make(img: BuildImage) -> BuildImage:
            return frame.copy().paste(
                img.resize((540, 360), keep_ratio=True), (368, 65), below=True
            )

        self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="我老婆 ",
        usage="我老婆 <QQ号或@对方>",
        permission="anyone",
        description="我老婆",
        mode="表  情  包"
    )
    def mywife(self):
        img = self.GetImage().convert("RGBA").resize_width(400)
        img_w, img_h = img.size
        frame = BuildImage.new("RGBA", (650, img_h + 500), "white")
        frame.paste(img, (int(325 - img_w / 2), 105), alpha=True)

        text = "如果你的老婆长这样"
        frame.draw_text(
            (27, 12, 27 + 596, 12 + 79),
            text,
            max_fontsize=70,
            min_fontsize=30,
            allow_wrap=True,
            lines_align="center",
            weight="bold",
        )
        text = "那么这就不是你的老婆\n这是我的老婆"
        frame.draw_text(
            (27, img_h + 120, 27 + 593, img_h + 120 + 135),
            text,
            max_fontsize=70,
            min_fontsize=30,
            allow_wrap=True,
            weight="bold",
        )
        text = "滚去找你\n自己的老婆去"
        frame.draw_text(
            (27, img_h + 295, 27 + 374, img_h + 295 + 135),
            text,
            max_fontsize=70,
            min_fontsize=30,
            allow_wrap=True,
            lines_align="center",
            weight="bold",
        )

        img_point = load_image("mywife/1.png").resize_width(200)
        frame.paste(img_point, (421, img_h + 270))

        self.save_and_send(frame)

    @RegCmd(
        name="字符画 ",
        usage="字符画 <QQ号或@对方>",
        permission="anyone",
        description="字符画",
        mode="表  情  包"
    )
    def charpic(self):
        img = self.GetImage()
        str_map = "@@$$&B88QMMGW##EE93SPPDOOU**==()+^,\"--''.  "
        num = len(str_map)
        font = Font.find("Consolas").load_font(15)

        def make(img: BuildImage) -> BuildImage:
            img = img.convert("L").resize_width(150)
            img = img.resize((img.width, img.height // 2))
            lines = []
            for y in range(img.height):
                line = ""
                for x in range(img.width):
                    gray = img.image.getpixel((x, y))
                    line += str_map[int(num * gray / 256)]
                lines.append(line)
            text = "\n".join(lines)
            w, h = font.getsize_multiline(text)
            text_img = Image.new("RGB", (w, h), "white")
            draw = ImageDraw.Draw(text_img)
            draw.multiline_text((0, 0), text, font=font, fill="black")
            return BuildImage(text_img)

        self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="防诱拐 ",
        usage="防诱拐 <QQ号或@对方>",
        permission="anyone",
        description="防诱拐",
        mode="表  情  包"
    )
    def anti_kidnap(self):
        img = self.GetImage()
        img = img.convert("RGBA").circle().resize((450, 450))
        bg = load_image("anti_kidnap/0.png")
        frame = BuildImage.new("RGBA", bg.size, "white")
        frame.paste(img, (30, 78))
        frame.paste(bg, alpha=True)
        self.save_and_send(frame)

    def make_gif(
            self,
            filename: str,
            pieces: Tuple[Tuple[int, int], ...],
            examples: Tuple[str, ...],
            fontsize: int = 20,
            padding_x: int = 5,
            padding_y: int = 5,
    ):
        texts = self.data.args[1:len(pieces) + 1]
        self.client.msg().raw("[CQ:reply,id={}] 玩命生成中...".format(self.data.se.get("message_id")))
        if not texts:
            texts = list(examples)
            self.client.msg().raw('您没有指定台词，将使用默认台词生成。默认台词：{}'.format(' '.join(texts)))

        if len(texts) != len(pieces):
            return self.client.msg().raw(f"该表情包需要加{len(pieces)}段文字，不加可查看示例图片")

        img = BuildImage.open(f"./resources/images/gif/{filename}").image
        frames: List[BuildImage] = []
        # self.send(dir(img))
        for i in range(img.n_frames):
            img.seek(i)
            frames.append(BuildImage(img.convert("RGB")))

        parts = [frames[start:end] for start, end in pieces]
        for part, text in zip(parts, texts):
            for frame in part:
                try:
                    frame.draw_text(
                        (padding_x, 0, frame.width - padding_x, frame.height - padding_y),
                        text,
                        max_fontsize=fontsize,
                        min_fontsize=fontsize,
                        fill="white",
                        stroke_ratio=0.05,
                        stroke_fill="black",
                        valign="bottom",
                    )
                except ValueError:
                    return self.client.msg().raw("<{}>这段话太长了～".format(text))

        self.save_gif([frame.image for frame in frames], img.info["duration"] / 1000)

    def gif_func(
            self,
            filename: str,
            pieces: Tuple[Tuple[int, int], ...],
            examples: Tuple[str, ...],
            **kwargs,
    ):
        try:
            self.make_gif(filename=filename, pieces=pieces, examples=examples, **kwargs)
        except Exception:
            self.client.msg().raw(traceback.format_exc())

    @RegCmd(
        name="王境泽",
        usage="王境泽 <台词，空格间隔>",
        permission="anyone",
        description="wangjingze",
        mode="文字表情"
    )
    def wangjingze(self):
        self.gif_func(
            "wangjingze.gif",
            ((0, 9), (12, 24), (25, 35), (37, 48)),
            ("我就是饿死", "死外边 从这里跳下去", "不会吃你们一点东西", "真香"),
        )

    @RegCmd(
        name="为所欲为",
        usage="为所欲为 <台词，空格间隔>",
        permission="anyone",
        description="weisuoyuwei",
        mode="文字表情"
    )
    def weisuoyuwei(self):
        self.gif_func(
            "weisuoyuwei.gif",
            ((11, 14), (27, 38), (42, 61), (63, 81), (82, 95), (96, 105), (111, 131), (145, 157), (157, 167),),
            ("好啊", "就算你是一流工程师", "就算你出报告再完美", "我叫你改报告你就要改", "毕竟我是客户",
             "客户了不起啊", "Sorry 客户真的了不起", "以后叫他天天改报告", "天天改 天天改"),
            fontsize=19,
        )

    @RegCmd(
        name="馋身子",
        usage="馋身子 <台词，空格间隔>",
        permission="anyone",
        description="馋身子",
        mode="文字表情"
    )
    def chanshenzi(self):
        self.gif_func(
            "chanshenzi.gif",
            ((0, 16), (16, 31), (33, 40)),
            ("你那叫喜欢吗？", "你那是馋她身子", "你下贱！"),
            fontsize=18,
        )

    @RegCmd(
        name="切格瓦拉",
        usage="切格瓦拉 <台词，空格间隔>",
        permission="anyone",
        description="切格瓦拉",
        mode="文字表情"
    )
    def qiegewala(self):
        self.gif_func(
            "qiegewala.gif",
            ((0, 15), (16, 31), (31, 38), (38, 48), (49, 68), (68, 86)),
            ("没有钱啊 肯定要做的啊", "不做的话没有钱用", "那你不会去打工啊", "有手有脚的", "打工是不可能打工的",
             "这辈子不可能打工的"),
        )

    @RegCmd(
        name="谁反对",
        usage="谁反对 <台词，空格间隔>",
        permission="anyone",
        description="谁反对",
        mode="文字表情"
    )
    def shuifandui(self):
        self.gif_func(
            "shuifandui.gif",
            ((3, 14), (21, 26), (31, 38), (40, 45)),
            ("我话说完了", "谁赞成", "谁反对", "我反对"),
            fontsize=19,
        )

    @RegCmd(
        name="曾小贤",
        usage="曾小贤 <台词，空格间隔>",
        permission="anyone",
        description="曾小贤",
        mode="文字表情"
    )
    def zengxiaoxian(self):
        self.gif_func(
            "zengxiaoxian.gif",
            ((3, 15), (24, 30), (30, 46), (56, 63)),
            ("平时你打电子游戏吗", "偶尔", "星际还是魔兽", "连连看"),
            fontsize=21,
        )

    @RegCmd(
        name="压力大爷",
        usage="压力大爷 <台词，空格间隔>",
        permission="anyone",
        description="压力大爷",
        mode="文字表情"
    )
    def yalidaye(self):
        self.gif_func(
            "yalidaye.gif",
            ((0, 16), (21, 47), (52, 77)),
            ("外界都说我们压力大", "我觉得吧压力也没有那么大", "主要是28岁了还没媳妇儿"),
            fontsize=21,
        )

    @RegCmd(
        name="你好骚啊",
        usage="你好骚啊 <台词，空格间隔>",
        permission="anyone",
        description="你好骚啊",
        mode="文字表情"
    )
    def nihaosaoa(self):
        self.gif_func(
            "nihaosaoa.gif",
            ((0, 14), (16, 26), (42, 61)),
            ("既然追求刺激", "就贯彻到底了", "你好骚啊"),
            fontsize=17,
        )

    @RegCmd(
        name="食屎啦你",
        usage="食屎啦你 <台词，空格间隔>",
        permission="anyone",
        description="食屎啦你",
        mode="文字表情"
    )
    def shishilani(self):
        self.gif_func(
            "shishilani.gif",
            ((14, 21), (23, 36), (38, 46), (60, 66)),
            ("穿西装打领带", "拿大哥大有什么用", "跟着这样的大哥", "食屎啦你"),
            fontsize=17,
        )

    @RegCmd(
        name="五年怎么过的",
        usage="五年怎么过的 <台词，空格间隔>",
        permission="anyone",
        description="五年怎么过的",
        mode="文字表情"
    )
    def wunian(self):
        self.gif_func(
            "wunian.gif",
            ((11, 20), (35, 50), (59, 77), (82, 95)),
            ("五年", "你知道我这五年是怎么过的吗", "我每天躲在家里玩贪玩蓝月", "你知道有多好玩吗"),
            fontsize=16,
        )

    @RegCmd(
        name="5000兆 ",
        usage="5000兆 <内容1> <内容2>",
        permission="anyone",
        description="5000兆",
        mode="文字表情"
    )
    def fivethousand_choyen(self):
        texts = self.data.args[1:3]
        fontsize = 200
        fontname = "Noto Sans SC"
        text = texts[0]
        pos_x = 40
        pos_y = 220
        imgs: List[Tuple[IMG, Tuple[int, int]]] = []

        def transform(img: IMG) -> IMG:
            skew = 0.45
            dw = round(img.height * skew)
            return img.transform(
                (img.width + dw, img.height),
                Image.AFFINE,
                (1, skew, -dw, 0, 1, 0),
                Image.BILINEAR,
            )

        def shift(t2m: Text2Image) -> Tuple[int, int]:
            return (
                pos_x
                - t2m.lines[0].chars[0].stroke_width
                - max(char.stroke_width for char in t2m.lines[0].chars),
                pos_y - t2m.lines[0].ascent,
            )

        def add_color_text(stroke_width: int, fill: str, pos: Tuple[int, int]):
            t2m = Text2Image.from_text(
                text, fontsize, fontname=fontname, stroke_width=stroke_width, fill=fill
            )
            dx, dy = shift(t2m)
            imgs.append((transform(t2m.to_image()), (dx + pos[0], dy + pos[1])))

        def add_gradient_text(
                stroke_width: int,
                dir: Tuple[int, int, int, int],
                color_stops: List[Tuple[float, Tuple[int, int, int]]],
                pos: Tuple[int, int],
        ):
            t2m = Text2Image.from_text(
                text, fontsize, fontname=fontname, stroke_width=stroke_width, fill="white"
            )
            mask = transform(t2m.to_image()).convert("L")
            dx, dy = shift(t2m)
            gradient = LinearGradient(
                (dir[0] - dx, dir[1] - dy, dir[2] - dx, dir[3] - dy),
                [ColorStop(*color_stop) for color_stop in color_stops],
            )
            bg = gradient.create_image(mask.size)
            bg.putalpha(mask)
            imgs.append((bg, (dx + pos[0], dy + pos[1])))

        # 黑
        add_color_text(22, "black", (8, 8))
        # 银
        add_gradient_text(
            20,
            (0, 38, 0, 234),
            [
                (0.0, (0, 15, 36)),
                (0.1, (255, 255, 255)),
                (0.18, (55, 58, 59)),
                (0.25, (55, 58, 59)),
                (0.5, (200, 200, 200)),
                (0.75, (55, 58, 59)),
                (0.85, (25, 20, 31)),
                (0.91, (240, 240, 240)),
                (0.95, (166, 175, 194)),
                (1, (50, 50, 50)),
            ],
            (8, 8),
        )
        # 黑
        add_color_text(16, "black", (0, 0))
        # 金
        add_gradient_text(
            10,
            (0, 40, 0, 200),
            [
                (0, (253, 241, 0)),
                (0.25, (245, 253, 187)),
                (0.4, (255, 255, 255)),
                (0.75, (253, 219, 9)),
                (0.9, (127, 53, 0)),
                (1, (243, 196, 11)),
            ],
            (0, 0),
        )
        # 黑
        add_color_text(6, "black", (4, -6))
        # 白
        add_color_text(6, "white", (0, -6))
        # 红
        add_gradient_text(
            4,
            (0, 50, 0, 200),
            [
                (0, (255, 100, 0)),
                (0.5, (123, 0, 0)),
                (0.51, (240, 0, 0)),
                (1, (5, 0, 0)),
            ],
            (0, -6),
        )
        # 红
        add_gradient_text(
            0,
            (0, 50, 0, 200),
            [
                (0, (230, 0, 0)),
                (0.5, (123, 0, 0)),
                (0.51, (240, 0, 0)),
                (1, (5, 0, 0)),
            ],
            (0, -6),
        )

        text = texts[1]
        fontname = "Noto Serif SC"
        pos_x = 300
        pos_y = 480
        # 黑
        add_color_text(22, "black", (10, 4))
        # 银
        add_gradient_text(
            19,
            (0, 320, 0, 506),
            [
                (0, (0, 15, 36)),
                (0.25, (250, 250, 250)),
                (0.5, (150, 150, 150)),
                (0.75, (55, 58, 59)),
                (0.85, (25, 20, 31)),
                (0.91, (240, 240, 240)),
                (0.95, (166, 175, 194)),
                (1, (50, 50, 50)),
            ],
            (10, 4),
        )
        # 黑
        add_color_text(17, "#10193A", (0, 0))
        # 白
        add_color_text(8, "#D0D0D0", (0, 0))
        # 绀
        add_gradient_text(
            7,
            (0, 320, 0, 480),
            [
                (0, (16, 25, 58)),
                (0.03, (255, 255, 255)),
                (0.08, (16, 25, 58)),
                (0.2, (16, 25, 58)),
                (1, (16, 25, 58)),
            ],
            (0, 0),
        )
        # 银
        add_gradient_text(
            0,
            (0, 320, 0, 480),
            [
                (0, (245, 246, 248)),
                (0.15, (255, 255, 255)),
                (0.35, (195, 213, 220)),
                (0.5, (160, 190, 201)),
                (0.51, (160, 190, 201)),
                (0.52, (196, 215, 222)),
                (1.0, (255, 255, 255)),
            ],
            (0, -6),
        )

        img_h = 580
        img_w = max([img.width + pos[0] for img, pos in imgs])
        frame = BuildImage.new("RGBA", (img_w, img_h), "white")
        for img, pos in imgs:
            frame.paste(img, pos, alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="google ",
        usage="google <内容>",
        permission="anyone",
        description="google",
        mode="文字表情"
    )
    def google(self):
        text = self.data.message
        text = " ".join(text.splitlines())
        colors = ["#4285f4", "#db4437", "#f4b400", "#4285f4", "#0f9d58", "#db4437"]
        t2m = Text2Image.from_text(text, 200)
        index = 0
        for char in t2m.lines[0].chars:
            char.fill = colors[index % len(colors)]
            if char.char.strip():
                index += 1
        self.save_and_send(BuildImage(t2m.to_image(bg_color="white", padding=(50, 50))))

    @RegCmd(
        name="youtube ",
        usage="youtube <内容1> <内容2>",
        permission="anyone",
        description="youtube",
        mode="文字表情"
    )
    def youtube(self):
        texts = self.data.args[1:3]
        left_img = Text2Image.from_text(texts[0], fontsize=200, fill="black").to_image(
            bg_color="white", padding=(30, 20)
        )

        right_img = Text2Image.from_text(
            texts[1], fontsize=200, fill="white", weight="bold"
        ).to_image(bg_color=(230, 33, 23), padding=(50, 20))
        right_img = BuildImage(right_img).resize_canvas(
            (max(right_img.width, 400), right_img.height), bg_color=(230, 33, 23)
        )
        right_img = right_img.circle_corner(right_img.height // 2)

        frame = BuildImage.new(
            "RGBA",
            (left_img.width + right_img.width, max(left_img.height, right_img.height)),
            "white",
        )
        frame.paste(left_img, (0, frame.height - left_img.height))
        frame = frame.resize_canvas(
            (frame.width + 100, frame.height + 100), bg_color="white"
        )

        corner = load_image("youtube/corner.png")
        ratio = right_img.height / 2 / corner.height
        corner = corner.resize((int(corner.width * ratio), int(corner.height * ratio)))
        x0 = left_img.width + 50
        y0 = frame.height - right_img.height - 50
        x1 = frame.width - corner.width - 50
        y1 = frame.height - corner.height - 50
        frame.paste(corner, (x0, y0 - 1), alpha=True).paste(
            corner.transpose(Image.FLIP_TOP_BOTTOM), (x0, y1 + 1), alpha=True
        ).paste(corner.transpose(Image.FLIP_LEFT_RIGHT), (x1, y0 - 1), alpha=True).paste(
            corner.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT),
            (x1, y1 + 1),
            alpha=True,
        ).paste(
            right_img, (x0, y0), alpha=True
        )
        self.save_and_send(frame)

    @RegCmd(
        name="pornhub ",
        usage="pornhub <内容1> <内容2>",
        permission="anyone",
        description="pornhub",
        mode="文字表情"
    )
    def pornhub(self):
        texts = self.data.args[1:3]
        left_img = Text2Image.from_text(texts[0], fontsize=200, fill="white").to_image(
            bg_color="black", padding=(20, 10)
        )

        right_img = Text2Image.from_text(
            texts[1], fontsize=200, fill="black", weight="bold"
        ).to_image(bg_color=(247, 152, 23), padding=(20, 10))
        right_img = BuildImage(right_img).circle_corner(20)

        frame = BuildImage.new(
            "RGBA",
            (left_img.width + right_img.width, max(left_img.height, right_img.height)),
            "black",
        )
        frame.paste(left_img, (0, frame.height - left_img.height)).paste(
            right_img, (left_img.width, frame.height - right_img.height), alpha=True
        )
        frame = frame.resize_canvas(
            (frame.width + 100, frame.height + 100), bg_color="black"
        )
        self.save_and_send(frame)

    @RegCmd(
        name="大鸭鸭举牌 ",
        usage="大鸭鸭举牌 <内容>",
        permission="anyone",
        description="大鸭鸭举牌",
        mode="文字表情"
    )
    def bronya_holdsign(self):
        text = self.data.message
        frame = load_image("bronya_holdsign/0.jpg")
        try:
            frame.draw_text(
                (190, 675, 640, 930),
                text,
                fill=(111, 95, 95),
                allow_wrap=True,
                max_fontsize=60,
                min_fontsize=25,
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="整点薯条 ",
        usage="整点薯条 <内容，四个参数，空格隔开>",
        permission="anyone",
        description="整点薯条",
        mode="文字表情"
    )
    def findchips(self):
        texts = self.data.args[1:5]
        frame = load_image("findchips/0.jpg")

        def draw(pos: Tuple[float, float, float, float], text: str):
            frame.draw_text(pos, text, max_fontsize=40, min_fontsize=20, allow_wrap=True)

        try:
            draw((405, 54, 530, 130), texts[0])
            draw((570, 62, 667, 160), texts[1])
            draw((65, 400, 325, 463), texts[2])
            draw((430, 400, 630, 470), texts[3])
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="许愿失败 ",
        usage="许愿失败 <内容>",
        permission="anyone",
        description="许愿失败",
        mode="文字表情"
    )
    def wish_fail(self):
        text = self.data.message
        frame = load_image("wish_fail/0.png")
        try:
            frame.draw_text(
                (70, 305, 320, 380),
                text,
                allow_wrap=True,
                max_fontsize=80,
                min_fontsize=20,
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="流星 ",
        usage="流星 <内容>",
        permission="anyone",
        description="流星",
        mode="文字表情"
    )
    def meteor(self):
        text = self.data.message
        frame = load_image("meteor/0.png")
        try:
            frame.draw_text(
                (220, 230, 920, 315),
                text,
                allow_wrap=True,
                max_fontsize=80,
                min_fontsize=20,
                fill="white",
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="快跑 ",
        usage="快跑 <内容>",
        permission="anyone",
        description="口号",
        mode="文字表情"
    )
    def run(self):
        text = self.data.message
        frame = load_image("run/0.png")
        text_img = BuildImage.new("RGBA", (122, 53))
        try:
            text_img.draw_text(
                (0, 0, 122, 53),
                text,
                allow_wrap=True,
                max_fontsize=50,
                min_fontsize=10,
                lines_align="center",
            )
        except ValueError:
            return OVER_LENGTH_MSG
        frame.paste(text_img.rotate(7, expand=True), (200, 195), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="升天 ",
        usage="升天 <内容>",
        permission="anyone",
        description="升天",
        mode="文字表情"
    )
    def ascension(self):
        text = self.data.message
        frame = load_image("ascension/0.png")
        text = f"你原本应该要去地狱的，但因为你生前{text}，我们就当作你已经服完刑期了"
        try:
            frame.draw_text(
                (40, 30, 482, 135),
                text,
                allow_wrap=True,
                max_fontsize=50,
                min_fontsize=20,
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="刮刮乐 ",
        usage="刮刮乐 <内容>",
        permission="anyone",
        description="刮刮乐",
        mode="文字表情"
    )
    def scratchoff(self):
        text = self.data.message
        frame = load_image("scratchoff/0.png")
        try:
            frame.draw_text(
                (80, 160, 360, 290),
                text,
                allow_wrap=True,
                max_fontsize=80,
                min_fontsize=30,
                fill="white",
                lines_align="center",
            )
        except ValueError:
            return OVER_LENGTH_MSG
        mask = load_image("scratchoff/1.png")
        frame.paste(mask, alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="可达鸭 ",
        usage="可达鸭 <内容1> <内容2>",
        permission="anyone",
        description="可达鸭",
        mode="文字表情"
    )
    def psyduck(self):
        texts = self.data.args[1:3]
        left_img = BuildImage.new("RGBA", (155, 100))
        right_img = BuildImage.new("RGBA", (155, 100))

        def draw(frame: BuildImage, text: str):
            frame.draw_text(
                (5, 5, 150, 95),
                text,
                max_fontsize=80,
                min_fontsize=30,
                allow_wrap=True,
                fontname="FZSJ-QINGCRJ",
            )

        try:
            draw(left_img, texts[0])
            draw(right_img, texts[1])
        except ValueError:
            return OVER_LENGTH_MSG
        except Exception:
            return self.send("该指令需要两个参数，以空格隔开")

        params = [
            ("left", ((0, 11), (154, 0), (161, 89), (20, 104)), (18, 42)),
            ("left", ((0, 9), (153, 0), (159, 89), (20, 101)), (15, 38)),
            ("left", ((0, 7), (148, 0), (156, 89), (21, 97)), (14, 23)),
            None,
            ("right", ((10, 0), (143, 17), (124, 104), (0, 84)), (298, 18)),
            ("right", ((13, 0), (143, 27), (125, 113), (0, 83)), (298, 30)),
            ("right", ((13, 0), (143, 27), (125, 113), (0, 83)), (298, 26)),
            ("right", ((13, 0), (143, 27), (125, 113), (0, 83)), (298, 30)),
            ("right", ((13, 0), (143, 27), (125, 113), (0, 83)), (302, 20)),
            ("right", ((13, 0), (141, 23), (120, 102), (0, 82)), (300, 24)),
            ("right", ((13, 0), (140, 22), (118, 100), (0, 82)), (299, 22)),
            ("right", ((9, 0), (128, 16), (109, 89), (0, 80)), (303, 23)),
            None,
            ("left", ((0, 13), (152, 0), (158, 89), (17, 109)), (35, 36)),
            ("left", ((0, 13), (152, 0), (158, 89), (17, 109)), (31, 29)),
            ("left", ((0, 17), (149, 0), (155, 90), (17, 120)), (45, 33)),
            ("left", ((0, 14), (152, 0), (156, 91), (17, 115)), (40, 27)),
            ("left", ((0, 12), (154, 0), (158, 90), (17, 109)), (35, 28)),
        ]

        frames: List[IMG] = []
        for i in range(18):
            frame = load_image(f"psyduck/{i}.jpg")
            param = params[i]
            if param:
                side, points, pos = param
                if side == "left":
                    frame.paste(left_img.perspective(points), pos, alpha=True)
                elif side == "right":
                    frame.paste(right_img.perspective(points), pos, alpha=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.2)

    @RegCmd(
        name="举牌 ",
        usage="举牌 <内容>",
        permission="anyone",
        description="举牌子",
        mode="文字表情"
    )
    def raisesign(self):
        text = self.data.message
        frame = load_image("raisesign/0.jpg")
        text_img = BuildImage.new("RGBA", (360, 260))
        try:
            text_img.draw_text(
                (10, 10, 350, 250),
                text,
                max_fontsize=80,
                min_fontsize=30,
                allow_wrap=True,
                lines_align="center",
                spacing=10,
                fontname="FZSEJW",
                fill="#51201b",
            )
        except ValueError:
            return OVER_LENGTH_MSG
        text_img = text_img.perspective(((33, 0), (375, 120), (333, 387), (0, 258)))
        frame.paste(text_img, (285, 24), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="起来了 ",
        usage="起来了 <内容>",
        permission="anyone",
        description="起来了",
        mode="文字表情"
    )
    def wakeup(self):
        text = self.data.message
        frame = load_image("wakeup/0.jpg")
        try:
            frame.draw_text((310, 270, 460, 380), text, max_fontsize=90, min_fontsize=50)
            frame.draw_text(
                (50, 610, 670, 720), f"{text}起来了", max_fontsize=110, min_fontsize=70
            )
        except ValueError:
            return
        self.save_and_send(frame)

    @RegCmd(
        name="douyin ",
        usage="douyin <内容>",
        permission="anyone",
        description="douyin",
        mode="文字表情"
    )
    def douyin(self):
        text = self.data.message
        text = " ".join(text.splitlines())
        fontsize = 200
        offset = round(fontsize * 0.05)
        px = 70
        py = 30
        bg_color = "#1C0B1B"
        frame = Text2Image.from_text(
            text, fontsize, fill="#FF0050", stroke_fill="#FF0050", stroke_width=5
        ).to_image(bg_color=bg_color, padding=(px + offset * 2, py + offset * 2, px, py))
        Text2Image.from_text(
            text, fontsize, fill="#00F5EB", stroke_fill="#00F5EB", stroke_width=5
        ).draw_on_image(frame, (px, py))
        Text2Image.from_text(
            text, fontsize, fill="white", stroke_fill="white", stroke_width=5
        ).draw_on_image(frame, (px + offset, py + offset))
        frame = BuildImage(frame)

        width = frame.width - px
        height = frame.height - py
        frame_num = 10
        devide_num = 6
        seed = 20 * 0.05
        frames: List[IMG] = []
        for _ in range(frame_num):
            new_frame = frame.copy()
            h_seeds = [
                math.fabs(math.sin(random.random() * devide_num)) for _ in range(devide_num)
            ]
            h_seed_sum = sum(h_seeds)
            h_seeds = [s / h_seed_sum for s in h_seeds]
            direction = 1
            last_yn = 0
            last_h = 0
            for i in range(devide_num):
                yn = last_yn + last_h
                h = max(round(height * h_seeds[i]), 2)
                last_yn = yn
                last_h = h
                direction = -direction
                piece = new_frame.copy().crop((px, yn, px + width, yn + h))
                new_frame.paste(piece, (px + round(i * direction * seed), yn))
            # 透视变换
            move_x = 64
            points = (
                (move_x, 0),
                (new_frame.width + move_x, 0),
                (new_frame.width, new_frame.height),
                (0, new_frame.height),
            )
            new_frame = new_frame.perspective(points)
            bg = BuildImage.new("RGBA", new_frame.size, bg_color)
            bg.paste(new_frame, alpha=True)
            frames.append(bg.image)

        self.save_gif(frames, 0.2)

    @RegCmd(
        name="不喊我 ",
        usage="不喊我 <内容>",
        permission="anyone",
        description="5000兆",
        mode="文字表情"
    )
    def not_call_me(self):
        text = self.data.message
        frame = load_image("not_call_me/0.png")
        try:
            frame.draw_text(
                (228, 11, 340, 164),
                text,
                allow_wrap=True,
                max_fontsize=80,
                min_fontsize=20,
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="口号 ",
        usage="口号 <内容，至少6条，空格间隔>",
        permission="anyone",
        description="口号",
        mode="文字表情"
    )
    def slogan(self):
        texts = self.data.args[1:7]
        frame = load_image("slogan/0.jpg")

        def draw(pos: Tuple[float, float, float, float], text: str):
            frame.draw_text(pos, text, max_fontsize=40, min_fontsize=15, allow_wrap=True)

        try:
            draw((10, 0, 294, 50), texts[0])
            draw((316, 0, 602, 50), texts[1])
            draw((10, 230, 294, 280), texts[2])
            draw((316, 230, 602, 280), texts[3])
            draw((10, 455, 294, 505), texts[4])
            draw((316, 455, 602, 505), texts[5])
        except ValueError:
            return OVER_LENGTH_MSG
        except Exception:
            return self.client.msg().raw("需要6个参数，以空格隔开哦")
        self.save_and_send(frame)

    @RegCmd(
        name="吴京 ",
        usage="吴京 <吴京内容> <中国内容>",
        permission="anyone",
        description="吴京xx中国xx",
        mode="文字表情"
    )
    def wujing(self):
        left = self.data.args[1]
        right = self.data.args[2]
        frame = load_image("wujing/0.jpg")

        def draw(
                pos: Tuple[float, float, float, float],
                text: str,
                align: Literal["left", "right", "center"],
        ):
            frame.draw_text(
                pos,
                text,
                halign=align,
                max_fontsize=100,
                min_fontsize=50,
                fill="white",
                stroke_fill="black",
                stroke_ratio=0.05,
            )

        try:
            if left:
                parts = left.split()
                if len(parts) >= 2:
                    draw((50, 430, 887, 550), " ".join(parts[:-1]), "left")
                draw((20, 560, 350, 690), parts[-1], "right")
            if right:
                parts = right.split()
                draw((610, 540, 917, 670), parts[0], "left")
                if len(parts) >= 2:
                    draw((50, 680, 887, 810), " ".join(parts[1:]), "center")
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="情商 ",
        usage="情商 <低情商内容> <高情商内容>",
        permission="anyone",
        description="情商姐",
        mode="文字表情"
    )
    def high_EQ(self):
        left = self.data.args[1]
        right = self.data.args[2]
        frame = load_image("high_EQ/0.jpg")

        def draw(pos: Tuple[float, float, float, float], text: str):
            frame.draw_text(
                pos,
                text,
                max_fontsize=100,
                min_fontsize=50,
                allow_wrap=True,
                fill="white",
                stroke_fill="black",
                stroke_ratio=0.05,
            )

        try:
            draw((40, 540, 602, 1140), left)
            draw((682, 540, 1244, 1140), right)
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="一巴掌 ",
        usage="一巴掌 <内容>",
        permission="anyone",
        description="一巴掌...",
        mode="文字表情"
    )
    def slap(self):
        text = self.data.message
        frame = load_image("slap/0.jpg")
        try:
            frame.draw_text(
                (20, 450, 620, 630),
                text,
                allow_wrap=True,
                max_fontsize=110,
                min_fontsize=50,
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="坐牢 ",
        usage="坐牢 <内容>",
        permission="anyone",
        description="坐牢...",
        mode="文字表情"
    )
    def imprison(self):
        text = self.data.message
        frame = load_image("imprison/0.jpg")
        try:
            frame.draw_text(
                (10, 157, 230, 197),
                text,
                allow_wrap=True,
                max_fontsize=35,
                min_fontsize=15,
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="滚屏 ",
        usage="滚屏 <内容>",
        permission="anyone",
        description="滚屏...",
        mode="文字表情"
    )
    def scroll(self):
        text = self.data.message
        text2image = Text2Image.from_text(text, 40).wrap(600)
        if len(text2image.lines) > 5:
            return OVER_LENGTH_MSG
        text_img = text2image.to_image()
        text_w, text_h = text_img.size

        box_w = text_w + 140
        box_h = max(text_h + 103, 150)
        box = BuildImage.new("RGBA", (box_w, box_h), "#eaedf4")
        corner1 = load_image("scroll/corner1.png")
        corner2 = load_image("scroll/corner2.png")
        corner3 = load_image("scroll/corner3.png")
        corner4 = load_image("scroll/corner4.png")
        box.paste(corner1, (0, 0))
        box.paste(corner2, (0, box_h - 75))
        box.paste(corner3, (text_w + 70, 0))
        box.paste(corner4, (text_w + 70, box_h - 75))
        box.paste(BuildImage.new("RGBA", (text_w, box_h - 40), "white"), (70, 20))
        box.paste(BuildImage.new("RGBA", (text_w + 88, box_h - 150), "white"), (27, 75))
        box.paste(text_img, (70, 17 + (box_h - 40 - text_h) // 2), alpha=True)

        dialog = BuildImage.new("RGBA", (box_w, box_h * 4), "#eaedf4")
        for i in range(4):
            dialog.paste(box, (0, box_h * i))

        frames: List[IMG] = []
        num = 30
        dy = int(dialog.height / num)
        for i in range(num):
            frame = BuildImage.new("RGBA", dialog.size)
            frame.paste(dialog, (0, -dy * i))
            frame.paste(dialog, (0, dialog.height - dy * i))
            frames.append(frame.image)
        self.save_gif(frames, 0.05)

    @RegCmd(
        name="别说了 ",
        usage="别说了 <内容>",
        permission="anyone",
        description="别说了...",
        mode="文字表情"
    )
    def shutup(self):
        text = self.data.message
        frame = load_image("shutup/0.jpg")
        try:
            frame.draw_text(
                (10, 180, 230, 230),
                text,
                allow_wrap=True,
                max_fontsize=40,
                min_fontsize=15,
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="低语 ",
        usage="低语 <内容>",
        permission="anyone",
        description="低语",
        mode="文字表情"
    )
    def murmur(self):
        text = self.data.message
        frame = load_image("murmur/0.png")
        try:
            frame.draw_text(
                (10, 255, 430, 300),
                text,
                max_fontsize=40,
                min_fontsize=15,
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="狂爱 ",
        usage="狂爱 <内容>",
        permission="anyone",
        description="狂粉",
        mode="文字表情"
    )
    def fanatic(self):
        text = self.data.message
        frame = load_image("fanatic/0.jpg")
        try:
            frame.draw_text(
                (145, 40, 343, 160),
                text,
                allow_wrap=True,
                lines_align="center",
                max_fontsize=70,
                min_fontsize=30,
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="悲报 ",
        usage="悲报 <内容>",
        permission="anyone",
        description="悲报",
        mode="文字表情"
    )
    def badnews(self):
        text = self.data.message
        frame = load_image("badnews/0.png")
        try:
            frame.draw_text(
                (50, 100, frame.width - 50, frame.height - 100),
                text,
                allow_wrap=True,
                lines_align="center",
                max_fontsize=60,
                min_fontsize=30,
                fill=(0, 0, 0),
                stroke_ratio=1 / 15,
                stroke_fill="white",
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="记仇 ",
        usage="记仇 <内容>",
        permission="anyone",
        description="这仇我记下了...",
        mode="文字表情"
    )
    def holdgrudge(self):
        text = self.data.message
        date = datetime.today().strftime("%Y{}%m{}%d{}").format("年", "月", "日")
        text = f"{date} 晴\n{text}\n这个仇我先记下了"
        text2image = Text2Image.from_text(text, 45, fill="black", spacing=10).wrap(440)
        if len(text2image.lines) > 10:
            return OVER_LENGTH_MSG
        text_img = text2image.to_image()

        frame = load_image("holdgrudge/0.png")
        bg = BuildImage.new(
            "RGB", (frame.width, frame.height + text_img.height + 20), "white"
        )
        bg.paste(frame).paste(text_img, (30, frame.height + 5), alpha=True)
        self.save_and_send(bg)

    @RegCmd(
        name="喜报 ",
        usage="喜报 <内容>",
        permission="anyone",
        description="喜报",
        mode="文字表情"
    )
    def goodnews(self):
        text = self.data.message
        frame = load_image("goodnews/0.jpg")
        try:
            frame.draw_text(
                (50, 100, frame.width - 50, frame.height - 100),
                text,
                allow_wrap=True,
                lines_align="center",
                max_fontsize=60,
                min_fontsize=30,
                fill=(238, 0, 0),
                stroke_ratio=1 / 15,
                stroke_fill=(255, 255, 153),
            )
        except ValueError:
            return OVER_LENGTH_MSG
        self.save_and_send(frame)

    @RegCmd(
        name="诺基亚 ",
        usage="诺基亚 <内容>",
        permission="anyone",
        description="有内鬼，停止交易",
        mode="文字表情"
    )
    def nokia(self):
        text = self.data.message[:900]
        text_img = (
            Text2Image.from_text(text, 70, fontname="FZXS14", fill="black", spacing=30)
            .wrap(700)
            .to_image()
        )
        text_img = (
            BuildImage(text_img)
            .resize_canvas((700, 450), direction="northwest")
            .rotate(-9.3, expand=True)
        )

        head_img = Text2Image.from_text(
            f"{len(text)}/900", 70, fontname="FZXS14", fill=(129, 212, 250, 255)
        ).to_image()
        head_img = BuildImage(head_img).rotate(-9.3, expand=True)

        frame = load_image("nokia/0.jpg")
        frame.paste(text_img, (205, 330), alpha=True)
        frame.paste(head_img, (790, 320), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="鲁迅说 ",
        usage="鲁迅说 <内容>",
        permission="anyone",
        description="鲁迅说过？",
        mode="文字表情"
    )
    def luxunsay(self):
        text = self.data.message
        frame = load_image("luxunsay/0.jpg")
        try:
            frame.draw_text(
                (40, frame.height - 200, frame.width - 40, frame.height - 100),
                text,
                allow_wrap=True,
                max_fontsize=40,
                min_fontsize=30,
                fill="white",
            )
        except ValueError:
            return OVER_LENGTH_MSG
        luxun_text = Text2Image.from_text("--鲁迅", 30, fill="white").to_image()
        frame.paste(luxun_text, (320, 400), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="摸 ",
        usage="摸 <QQ号或@对方>",
        permission="anyone",
        description="生成摸头像的表情包",
        mode="表  情  包"
    )
    def petpet(self):
        img = self.GetImage()
        img = img.convert("RGBA").square().circle()

        frames: List[IMG] = []
        locs = [
            (14, 20, 98, 98),
            (12, 33, 101, 85),
            (8, 40, 110, 76),
            (10, 33, 102, 84),
            (12, 20, 98, 98),
        ]
        for i in range(5):
            hand = self.load_image(f"petpet/{i}.png")
            frame = BuildImage.new("RGBA", hand.size, (255, 255, 255, 0))
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), alpha=True)
            frame.paste(hand, alpha=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.06)

    @RegCmd(
        name="滚 ",
        usage="滚 <QQ号或@对方>",
        permission="anyone",
        description="滚某个人的头像",
        mode="表  情  包"
    )
    def roll(self):
        img = self.GetImage()
        img = img.convert("RGBA").square().resize((210, 210))
        # fmt: off
        locs = [
            (87, 77, 0), (96, 85, -45), (92, 79, -90), (92, 78, -135),
            (92, 75, -180), (92, 75, -225), (93, 76, -270), (90, 80, -315)
        ]
        # fmt: on
        frames: List[IMG] = []
        for i in range(8):
            frame = self.load_image(f"roll/{i}.png")
            x, y, a = locs[i]
            frame.paste(img.rotate(a), (x, y), below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.06)

    @RegCmd(
        name="小天使 ",
        usage="小天使 <QQ号或@对方>",
        permission="anyone",
        description="生成小天使图片",
        mode="表  情  包"
    )
    def littleangel(self):
        userid = self.data.message
        if 'at' in userid:
            userid = CQCode(userid).get("qq")[0]

        username = self.GetUserInfo(userid).get('nickname')
        img = self.GetImage().convert("RGBA").resize_width(500)
        img_w, img_h = img.size
        frame = BuildImage.new("RGBA", (600, img_h + 230), "white")
        frame.paste(img, (int(300 - img_w / 2), 110), alpha=True)

        text = "非常可爱！简直就是小天使"
        frame.draw_text(
            (10, img_h + 120, 590, img_h + 185), text, max_fontsize=48, weight="bold"
        )

        text = f"Ta没失踪也没怎么样  我只是觉得你们都该看一下"
        frame.draw_text(
            (20, img_h + 180, 580, img_h + 215), text, max_fontsize=26, weight="bold"
        )

        text = f"请问你们看到{username}了吗?"
        try:
            frame.draw_text(
                (20, 0, 580, 110), text, max_fontsize=70, min_fontsize=25, weight="bold"
            )
        except ValueError:
            return self.send(NAME_TOO_LONG)

        self.save_and_send(frame)

    @RegCmd(
        name="警察 ",
        usage="警察 <QQ号或@对方>",
        permission="anyone",
        description="出警！",
        mode="表  情  包"
    )
    def police1(self):
        img = self.GetImage()
        img = img.convert("RGBA").resize((60, 75), keep_ratio=True).rotate(16, expand=True)
        frame = self.load_image("police/1.png")
        frame.paste(img, (37, 291), below=True)

        self.save_and_send(frame)

    @RegCmd(
        name="兑换卷 ",
        usage="兑换卷 <QQ号或@对方>",
        permission="anyone",
        description="XX陪睡兑换卷！",
        mode="表  情  包"
    )
    def coupon(self):
        userid = self.data.message
        if 'at' in userid:
            userid = CQCode(userid).get("qq")[0]

        username = self.GetUserInfo(userid).get('nickname')

        text = (f"{username}陪睡券") + "\n（永久有效）"
        text_img = BuildImage.new("RGBA", (250, 100))
        try:
            text_img.draw_text(
                (0, 0, text_img.width, text_img.height),
                text,
                lines_align="center",
                max_fontsize=30,
                min_fontsize=15,
            )
        except ValueError:
            return self.client.msg().raw(NAME_TOO_LONG)

        frame = self.load_image("coupon/0.png")
        img = self.GetImage().convert("RGBA").circle().resize((60, 60)).rotate(22, expand=True)
        frame.paste(img, (164, 85), alpha=True)
        frame.paste(text_img.rotate(22, expand=True), (94, 108), alpha=True)

        self.save_and_send(frame)

    @RegCmd(
        name="听音乐 ",
        usage="听音乐 <QQ号或@对方>",
        permission="anyone",
        description="听音乐！",
        mode="表  情  包"
    )
    def listen_music(self):
        img = self.GetImage().convert("RGBA")
        frame = self.load_image("listen_music/0.png")
        frames: List[IMG] = []
        for i in range(0, 360, 10):
            frames.append(
                frame.copy()
                .paste(img.rotate(-i).resize((215, 215)), (100, 100), below=True)
                .image
            )
        self.save_gif(frames, 0.05)

    @RegCmd(
        name="扔 ",
        usage="扔 <QQ号或@对方>",
        permission="anyone",
        description="扔某人的头像",
        mode="表  情  包"
    )
    def throw_gif(self):
        img = self.GetImage().convert("RGBA").circle()
        locs = [
            [(32, 32, 108, 36)],
            [(32, 32, 122, 36)],
            [],
            [(123, 123, 19, 129)],
            [(185, 185, -50, 200), (33, 33, 289, 70)],
            [(32, 32, 280, 73)],
            [(35, 35, 259, 31)],
            [(175, 175, -50, 220)],
        ]
        frames: List[IMG] = []
        for i in range(8):
            frame = self.load_image(f"throw_gif/{i}.png")
            for w, h, x, y in locs[i]:
                frame.paste(img.resize((w, h)), (x, y), alpha=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.1)

    @RegCmd(
        name="吃 ",
        usage="吃 <QQ号或@对方>",
        permission="anyone",
        description="吃掉它！",
        mode="表  情  包"
    )
    def eat(self):
        img = self.GetImage().convert("RGBA").square().resize((32, 32))
        frames = []
        for i in range(3):
            frame = self.load_image(f"eat/{i}.png")
            frame.paste(img, (1, 38), below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.05)

    @RegCmd(
        name="我朋友说 ",
        usage="我朋友说 <QQ号或@对方> <说的内容>",
        permission="anyone",
        description="我有个朋友说...",
        mode="表  情  包"
    )
    def my_friend(self):
        userid = self.data.args[1]
        if 'at' in userid:
            userid = CQCode(userid).get("qq")[0]

        name = self.GetUserInfo(userid).get('nickname')
        texts = self.data.args[2]
        for i in self.data.args:
            if i == self.data.args[0] or i == self.data.args[1] or i == self.data.args[2]:
                continue
            texts += " {0}".format(i)
        img = self.GetImage().convert("RGBA").circle().resize((100, 100))

        name_img = Text2Image.from_text(name, 25, fill="#868894").to_image()
        name_w, name_h = name_img.size
        if name_w >= 700:
            raise ValueError(NAME_TOO_LONG)

        corner1 = self.load_image("my_friend/corner1.png")
        corner2 = self.load_image("my_friend/corner2.png")
        corner3 = self.load_image("my_friend/corner3.png")
        corner4 = self.load_image("my_friend/corner4.png")
        label = self.load_image("my_friend/label.png")

        def make_dialog(text: str) -> BuildImage:
            text_img = Text2Image.from_text(text, 40).wrap(700).to_image()
            text_w, text_h = text_img.size
            box_w = max(text_w, name_w + 15) + 140
            box_h = max(text_h + 103, 150)
            box = BuildImage.new("RGBA", (box_w, box_h))
            box.paste(corner1, (0, 0))
            box.paste(corner2, (0, box_h - 75))
            box.paste(corner3, (text_w + 70, 0))
            box.paste(corner4, (text_w + 70, box_h - 75))
            box.paste(BuildImage.new("RGBA", (text_w, box_h - 40), "white"), (70, 20))
            box.paste(BuildImage.new("RGBA", (text_w + 88, box_h - 150), "white"), (27, 75))
            box.paste(text_img, (70, 16 + (box_h - 40 - text_h) // 2), alpha=True)

            dialog = BuildImage.new("RGBA", (box.width + 130, box.height + 60), "#eaedf4")
            dialog.paste(img, (20, 20), alpha=True)
            dialog.paste(box, (130, 60), alpha=True)
            dialog.paste(label, (160, 25))
            dialog.paste(name_img, (260, 22 + (35 - name_h) // 2), alpha=True)
            return dialog

        if '|' in texts:
            texts = texts.split('|')
            dialogs = [make_dialog(text) for text in texts]
        else:
            dialogs = [make_dialog(texts)]
        frame_w = max((dialog.width for dialog in dialogs))
        frame_h = sum((dialog.height for dialog in dialogs))
        frame = BuildImage.new("RGBA", (frame_w, frame_h), "#eaedf4")
        current_h = 0
        for dialog in dialogs:
            frame.paste(dialog, (0, current_h))
            current_h += dialog.height
        self.save_and_send(frame)

    @RegCmd(
        name="假冒伪劣 ",
        usage="假冒伪劣 <昵称> <说的内容> <头像>",
        permission="anyone",
        description="生成对话图片",
        mode="表  情  包"
    )
    def make_dialog_picture(self):
        name = self.data.args[1]
        texts = self.data.args[2]
        url = self.data.args[3]
        image_bytes = urlopen(url).read()
        # internal data file
        data_stream = BytesIO(image_bytes)
        # open as a PIL image object
        # 以一个PIL图像对象打开
        img = BuildImage.open(data_stream).convert("RGBA").square().circle().resize((100, 100))

        name_img = Text2Image.from_text(name, 25, fill="#868894").to_image()
        name_w, name_h = name_img.size
        if name_w >= 700:
            raise ValueError(NAME_TOO_LONG)

        corner1 = self.load_image("my_friend/corner1.png")
        corner2 = self.load_image("my_friend/corner2.png")
        corner3 = self.load_image("my_friend/corner3.png")
        corner4 = self.load_image("my_friend/corner4.png")
        label = self.load_image("my_friend/label.png")

        def make_dialog(text: str) -> BuildImage:
            text_img = Text2Image.from_text(text, 40).wrap(700).to_image()
            text_w, text_h = text_img.size
            box_w = max(text_w, name_w + 15) + 140
            box_h = max(text_h + 103, 150)
            box = BuildImage.new("RGBA", (box_w, box_h))
            box.paste(corner1, (0, 0))
            box.paste(corner2, (0, box_h - 75))
            box.paste(corner3, (text_w + 70, 0))
            box.paste(corner4, (text_w + 70, box_h - 75))
            box.paste(BuildImage.new("RGBA", (text_w, box_h - 40), "white"), (70, 20))
            box.paste(BuildImage.new("RGBA", (text_w + 88, box_h - 150), "white"), (27, 75))
            box.paste(text_img, (70, 16 + (box_h - 40 - text_h) // 2), alpha=True)

            dialog = BuildImage.new("RGBA", (box.width + 130, box.height + 60), "#eaedf4")
            dialog.paste(img, (20, 20), alpha=True)
            dialog.paste(box, (130, 60), alpha=True)
            dialog.paste(label, (160, 25))
            dialog.paste(name_img, (260, 22 + (35 - name_h) // 2), alpha=True)
            return dialog

        if '|' in texts:
            texts = texts.split('|')
            dialogs = [make_dialog(text) for text in texts]
        else:
            dialogs = [make_dialog(texts)]
        frame_w = max((dialog.width for dialog in dialogs))
        frame_h = sum((dialog.height for dialog in dialogs))
        frame = BuildImage.new("RGBA", (frame_w, frame_h), "#eaedf4")
        current_h = 0
        for dialog in dialogs:
            frame.paste(dialog, (0, current_h))
            current_h += dialog.height
        self.save_and_send(frame)

    @RegCmd(
        name="亲 ",
        usage="亲 <QQ号或@对方>",
        permission="anyone",
        description="亲Ta！",
        mode="表  情  包"
    )
    def kiss(self):
        user_head = self.GetImage().convert("RGBA").circle().resize((50, 50))
        self.data.message = str(self.data.se.get('user_id'))
        self_head = self.GetImage().convert("RGBA").circle().resize((40, 40))
        # fmt: off
        user_locs = [
            (58, 90), (62, 95), (42, 100), (50, 100), (56, 100), (18, 120), (28, 110),
            (54, 100), (46, 100), (60, 100), (35, 115), (20, 120), (40, 96)
        ]
        self_locs = [
            (92, 64), (135, 40), (84, 105), (80, 110), (155, 82), (60, 96), (50, 80),
            (98, 55), (35, 65), (38, 100), (70, 80), (84, 65), (75, 65)
        ]
        # fmt: on
        frames: List[IMG] = []
        for i in range(13):
            frame = self.load_image(f"kiss/{i}.png")
            frame.paste(user_head, user_locs[i], alpha=True)
            frame.paste(self_head, self_locs[i], alpha=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.05)

    @RegCmd(
        name="贴贴 ",
        usage="贴贴 <QQ号或@对方>",
        permission="anyone",
        description="贴贴对方！",
        mode="表  情  包"
    )
    def rub(self):
        user_head = self.GetImage().convert("RGBA").circle().resize((50, 50))
        self.data.message = str(self.data.se.get('user_id'))
        self_head = self.GetImage().convert("RGBA").circle().resize((40, 40))
        # fmt: off
        user_locs = [
            (39, 91, 75, 75), (49, 101, 75, 75), (67, 98, 75, 75),
            (55, 86, 75, 75), (61, 109, 75, 75), (65, 101, 75, 75)
        ]
        self_locs = [
            (102, 95, 70, 80, 0), (108, 60, 50, 100, 0), (97, 18, 65, 95, 0),
            (65, 5, 75, 75, -20), (95, 57, 100, 55, -70), (109, 107, 65, 75, 0)
        ]
        # fmt: on
        frames: List[IMG] = []
        for i in range(6):
            frame = self.load_image(f"rub/{i}.png")
            x, y, w, h = user_locs[i]
            frame.paste(user_head.resize((w, h)), (x, y), alpha=True)
            x, y, w, h, angle = self_locs[i]
            frame.paste(
                self_head.resize((w, h)).rotate(angle, expand=True), (x, y), alpha=True
            )
            frames.append(frame.image)
        self.save_gif(frames, 0.05)

    @RegCmd(
        name="顶 ",
        usage="顶 <QQ号或@对方>",
        permission="anyone",
        description="顶",
        mode="表  情  包"
    )
    def play(self):
        img = self.GetImage().convert("RGBA").square()
        # fmt: off
        locs = [
            (180, 60, 100, 100), (184, 75, 100, 100), (183, 98, 100, 100),
            (179, 118, 110, 100), (156, 194, 150, 48), (178, 136, 122, 69),
            (175, 66, 122, 85), (170, 42, 130, 96), (175, 34, 118, 95),
            (179, 35, 110, 93), (180, 54, 102, 93), (183, 58, 97, 92),
            (174, 35, 120, 94), (179, 35, 109, 93), (181, 54, 101, 92),
            (182, 59, 98, 92), (183, 71, 90, 96), (180, 131, 92, 101)
        ]
        # fmt: on
        raw_frames: List[BuildImage] = [self.load_image(f"play/{i}.png") for i in range(23)]
        img_frames: List[BuildImage] = []
        for i in range(len(locs)):
            frame = raw_frames[i]
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), below=True)
            img_frames.append(frame)
        frames = (
                img_frames[0:12]
                + img_frames[0:12]
                + img_frames[0:8]
                + img_frames[12:18]
                + raw_frames[18:23]
        )
        frames = [frame.image for frame in frames]
        self.save_gif(frames, 0.06)

    @RegCmd(
        name="拍 ",
        usage="拍 <QQ号或@对方>",
        permission="anyone",
        description="拍",
        mode="表  情  包"
    )
    def pat(self):
        img = self.GetImage().convert("RGBA").square()
        locs = [(11, 73, 106, 100), (8, 79, 112, 96)]
        img_frames: List[IMG] = []
        for i in range(10):
            frame = self.load_image(f"pat/{i}.png")
            x, y, w, h = locs[1] if i == 2 else locs[0]
            frame.paste(img.resize((w, h)), (x, y), below=True)
            img_frames.append(frame.image)
        # fmt: off
        seq = [0, 1, 2, 3, 1, 2, 3, 0, 1, 2, 3, 0, 0, 1, 2, 3, 0, 0, 0, 0, 4, 5, 5, 5, 6, 7, 8, 9]
        # fmt: on
        frames = [img_frames[n] for n in seq]
        return self.save_gif(frames, 0.085)

    @RegCmd(
        name="撕 ",
        usage="撕 <QQ号或@对方>",
        permission="anyone",
        description="撕",
        mode="表  情  包"
    )
    def rip(self):
        img = self.GetImage().convert("RGBA").square().resize((385, 385))
        frame = self.load_image("rip/0.png")
        frame.paste(img.rotate(24, expand=True), (-5, 355), below=True)
        frame.paste(img.rotate(-11, expand=True), (649, 310), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="爬 ",
        usage="爬 <QQ号或@对方>",
        permission="anyone",
        description="爬",
        mode="表  情  包"
    )
    def crawl(self):
        total_num = 92
        num = random.randint(1, total_num)

        img = self.GetImage().convert("RGBA").circle().resize((100, 100))
        frame = self.load_image(f"crawl/{num:02d}.jpg")
        frame.paste(img, (0, 400), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="精神支柱 ",
        usage="精神支柱 <QQ号或@对方>",
        permission="anyone",
        description="精神支柱",
        mode="表  情  包"
    )
    def support(self):
        img = self.GetImage().convert("RGBA").square().resize((815, 815)).rotate(23, expand=True)
        frame = self.load_image("support/0.png")
        frame.paste(img, (-172, -17), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="一直 ",
        usage="一直 <QQ号或@对方>",
        permission="anyone",
        description="一直",
        mode="表  情  包"
    )
    def always(self):
        def make(img: BuildImage) -> BuildImage:
            img_big = img.resize_width(500)
            img_small = img.resize_width(100)
            h1 = img_big.height
            h2 = max(img_small.height, 80)
            frame = BuildImage.new("RGBA", (500, h1 + h2 + 10), "white")
            frame.paste(img_big, alpha=True).paste(img_small, (290, h1 + 5), alpha=True)
            frame.draw_text(
                (20, h1 + 5, 280, h1 + h2 + 5), "要我一直", halign="right", max_fontsize=60
            )
            frame.draw_text(
                (400, h1 + 5, 480, h1 + h2 + 5), "吗", halign="left", max_fontsize=60
            )
            return frame

        return self.make_jpg_or_gif(self.GetImage(), make)

    @RegCmd(
        name="加载中 ",
        usage="加载中 <QQ号或@对方>",
        permission="anyone",
        description="加载中",
        mode="表  情  包"
    )
    def loading(self):
        img = self.GetImage()
        img_big = img.convert("RGBA").resize_width(500)
        img_big = img_big.filter(ImageFilter.GaussianBlur(radius=3))
        h1 = img_big.height
        mask = BuildImage.new("RGBA", img_big.size, (0, 0, 0, 128))
        icon = self.load_image("loading/icon.png")
        img_big.paste(mask, alpha=True).paste(icon, (200, int(h1 / 2) - 50), alpha=True)

        def make(img: BuildImage) -> BuildImage:
            img_small = img.resize_width(100)
            h2 = max(img_small.height, 80)
            frame = BuildImage.new("RGBA", (500, h1 + h2 + 10), "white")
            frame.paste(img_big, alpha=True).paste(img_small, (100, h1 + 5), alpha=True)
            frame.draw_text(
                (210, h1 + 5, 480, h1 + h2 + 5), "不出来", halign="left", max_fontsize=60
            )
            return frame

        return self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="转 ",
        usage="转 <QQ号或@对方>",
        permission="anyone",
        description="转",
        mode="表  情  包"
    )
    def turn(self):
        img = self.GetImage().convert("RGBA").circle()
        frames: List[IMG] = []
        for i in range(0, 360, 10):
            frame = BuildImage.new("RGBA", (250, 250), "white")
            frame.paste(img.rotate(i).resize((250, 250)), alpha=True)
            frames.append(frame.image)
        if random.randint(0, 1):
            frames.reverse()
        return self.save_gif(frames, 0.05)

    @RegCmd(
        name="不要靠近 ",
        usage="不要靠近 <QQ号或@对方>",
        permission="anyone",
        description="不要靠近",
        mode="表  情  包"
    )
    def dont_touch(self):
        img = self.GetImage().convert("RGBA").square().resize((170, 170))
        frame = self.load_image("dont_touch/0.png")
        frame.paste(img, (23, 231), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="一样 ",
        usage="一样 <QQ号或@对方>",
        permission="anyone",
        description="一样",
        mode="表  情  包"
    )
    def alike(self):
        img = self.GetImage().convert("RGBA").square().resize((90, 90))
        frame = self.load_image("alike/0.png")
        frame.paste(img, (131, 14), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="玩游戏 ",
        usage="玩游戏 <QQ号或@对方>",
        permission="anyone",
        description="玩游戏",
        mode="表  情  包"
    )
    def play_game(self):
        text = "来玩休闲游戏啊"
        frame = self.load_image("play_game/0.png")
        try:
            frame.draw_text(
                (20, frame.height - 70, frame.width - 20, frame.height),
                text,
                max_fontsize=40,
                min_fontsize=25,
                stroke_fill="white",
                stroke_ratio=0.06,
            )
        except:
            return TEXT_TOO_LONG

        def make(img: BuildImage) -> BuildImage:
            points = ((0, 5), (227, 0), (216, 150), (0, 165))
            screen = img.resize((220, 160), keep_ratio=True).perspective(points)
            return frame.copy().paste(screen.rotate(9, expand=True), (161, 117), below=True)

        return self.make_jpg_or_gif(self.GetImage(), make)

    @RegCmd(
        name="膜 ",
        usage="膜 <QQ号或@对方>",
        permission="anyone",
        description="膜",
        mode="表  情  包"
    )
    def worship(self):
        img = self.GetImage().convert("RGBA")
        points = ((0, -30), (135, 17), (135, 145), (0, 140))
        paint = img.square().resize((150, 150)).perspective(points)
        frames: List[IMG] = []
        for i in range(10):
            frame = self.load_image(f"worship/{i}.png")
            frame.paste(paint, below=True)
            frames.append(frame.image)
        return self.save_gif(frames, 0.04)

    @RegCmd(
        name="万能表情 ",
        usage="万能表情 <QQ号或@对方> <附加文字>",
        permission="anyone",
        description="万能表情",
        mode="表  情  包"
    )
    def universal(self):
        args = self.data.args[2].split('|')
        img = self.GetImage()

        if not args:
            args = ["在此处添加文字"]

        def make(img: BuildImage) -> BuildImage:
            img = img.resize_width(500)
            frames: List[BuildImage] = [img]
            for arg in args:
                text_img = BuildImage(
                    Text2Image.from_bbcode_text(arg, fontsize=45, align="center")
                    .wrap(480)
                    .to_image()
                )
                frames.append(text_img.resize_canvas((500, text_img.height)))

            frame = BuildImage.new(
                "RGBA", (500, sum((f.height for f in frames)) + 10), "white"
            )
            current_h = 0
            for f in frames:
                frame.paste(f, (0, current_h), alpha=True)
                current_h += f.height
            return frame

        return self.make_jpg_or_gif(img, make)

    @RegCmd(
        name="啃 ",
        usage="啃 <QQ号或@对方>",
        permission="anyone",
        description="啃",
        mode="表  情  包"
    )
    def bite(self):
        img = self.GetImage().convert("RGBA").square()
        frames: List[IMG] = []
        # fmt: off
        locs = [
            (90, 90, 105, 150), (90, 83, 96, 172), (90, 90, 106, 148),
            (88, 88, 97, 167), (90, 85, 89, 179), (90, 90, 106, 151)
        ]
        # fmt: on
        for i in range(6):
            frame = self.load_image(f"bite/{i}.png")
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), below=True)
            frames.append(frame.image)
        for i in range(6, 16):
            frame = self.load_image(f"bite/{i}.png")
            frames.append(frame.image)
        return self.save_gif(frames, 0.07)

    @RegCmd(
        name="出警 ",
        usage="出警 <QQ号或@对方>",
        permission="anyone",
        description="出警",
        mode="表  情  包"
    )
    def police(self):
        img = self.GetImage().convert("RGBA").square().resize((245, 245))
        frame = self.load_image("police/0.png")
        frame.paste(img, (224, 46), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="问问 ",
        usage="问问 <QQ号或@对方>",
        permission="anyone",
        description="问问",
        mode="表  情  包"
    )
    def ask(self):
        img = self.GetImage().resize_width(640)
        img_w, img_h = img.size
        gradient_h = 150
        gradient = LinearGradient(
            (0, 0, 0, gradient_h),
            [ColorStop(0, (0, 0, 0, 220)), ColorStop(1, (0, 0, 0, 30))],
        )
        gradient_img = gradient.create_image((img_w, gradient_h))
        mask = BuildImage.new("RGBA", img.size)
        mask.paste(gradient_img, (0, img_h - gradient_h), alpha=True)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=3))
        img.paste(mask, alpha=True)

        userid = self.data.message
        if 'at' in userid:
            userid = CQCode(userid).get("qq")[0]

        userinfo = self.GetUserInfo(userid)
        name = userinfo.get('nickname')
        ta = "他" if userinfo.get('sex') == "male" else "她"

        start_w = 20
        start_h = img_h - gradient_h + 5
        text_img1 = Text2Image.from_text(f"{name}", 28, fill="orange", weight="bold").to_image()
        text_img2 = Text2Image.from_text(
            f"{name}不知道哦。", 28, fill="white", weight="bold"
        ).to_image()
        img.paste(
            text_img1,
            (start_w + 40 + (text_img2.width - text_img1.width) // 2, start_h),
            alpha=True,
        )
        img.paste(
            text_img2,
            (start_w + 40, start_h + text_img1.height + 10),
            alpha=True,
        )

        line_h = start_h + text_img1.height + 5
        img.draw_line(
            (start_w, line_h, start_w + text_img2.width + 80, line_h),
            fill="orange",
            width=2,
        )

        sep_w = 30
        sep_h = 80
        frame = BuildImage.new("RGBA", (img_w + sep_w * 2, img_h + sep_h * 2), "white")
        try:
            frame.draw_text(
                (sep_w, 0, img_w + sep_w, sep_h),
                f"让{name}告诉你吧",
                max_fontsize=35,
                halign="left",
            )
            frame.draw_text(
                (sep_w, img_h + sep_h, img_w + sep_w, img_h + sep_h * 2),
                f"啊这，{ta}说不知道",
                max_fontsize=35,
                halign="left",
            )
        except ValueError:
            return self.send(NAME_TOO_LONG)
        frame.paste(img, (sep_w, sep_h))
        self.save_and_send(frame)

    @RegCmd(
        name="舔 ",
        usage="舔 <QQ号或@对方>",
        permission="anyone",
        description="舔",
        mode="表  情  包"
    )
    def prpr(self):
        frame = self.load_image("prpr/0.png")

        def make(img: BuildImage) -> BuildImage:
            points = ((0, 19), (236, 0), (287, 264), (66, 351))
            screen = img.resize((330, 330), keep_ratio=True).perspective(points)
            return frame.copy().paste(screen, (56, 284), below=True)

        return self.make_jpg_or_gif(self.GetImage(), make)

    @RegCmd(
        name="搓 ",
        usage="搓 <QQ号或@对方>",
        permission="anyone",
        description="搓",
        mode="表  情  包"
    )
    def twist(self):
        img = self.GetImage().convert("RGBA").square().resize((78, 78))
        # fmt: off
        locs = [
            (25, 66, 0), (25, 66, 60), (23, 68, 120),
            (20, 69, 180), (22, 68, 240), (25, 66, 300)
        ]
        # fmt: on
        frames: List[IMG] = []
        for i in range(5):
            frame = self.load_image(f"twist/{i}.png")
            x, y, a = locs[i]
            frame.paste(img.rotate(a), (x, y), below=True)
            frames.append(frame.image)
        return self.save_gif(frames, 0.1)

    @RegCmd(
        name="墙纸 ",
        usage="墙纸 <QQ号或@对方>",
        permission="anyone",
        description="墙纸",
        mode="表  情  包"
    )
    def wallpaper(self):
        frame = self.load_image("wallpaper/0.png")

        def make(img: BuildImage) -> BuildImage:
            return frame.copy().paste(
                img.resize((775, 496), keep_ratio=True), (260, 580), below=True
            )

        return self.make_jpg_or_gif(self.GetImage(), make, gif_zoom=0.5)

    def china_flag(self):
        frame = self.load_image("china_flag/0.png")
        frame.paste(self.GetImage().convert("RGBA").resize(frame.size, keep_ratio=True), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="交个朋友 ",
        usage="交个朋友 <QQ号或@对方>",
        permission="anyone",
        description="交个朋友",
        mode="表  情  包"
    )
    def make_friend(self):
        img = self.GetImage().convert("RGBA")

        bg = self.load_image("make_friend/0.png")
        frame = img.resize_width(1000)
        frame.paste(
            img.resize_width(250).rotate(9, expand=True),
            (743, frame.height - 155),
            alpha=True,
        )
        frame.paste(
            img.square().resize((55, 55)).rotate(9, expand=True),
            (836, frame.height - 278),
            alpha=True,
        )
        frame.paste(bg, (0, frame.height - 1000), alpha=True)

        userid = self.data.message
        if 'at' in userid:
            userid = CQCode(userid).get("qq")[0]

        name = self.GetUserInfo(userid).get('nickname')
        text_img = Text2Image.from_text(name, 20, fill="white").to_image()
        if text_img.width > 230:
            return self.client.msg().raw(NAME_TOO_LONG)

        text_img = BuildImage(text_img).rotate(9, expand=True)
        frame.paste(text_img, (710, frame.height - 308), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="继续干活 ",
        usage="继续干活 <QQ号或@对方>",
        permission="anyone",
        description="继续干活",
        mode="表  情  包"
    )
    def back_to_work(self):
        frame = self.load_image("back_to_work/0.png")
        img = self.GetImage().convert("RGBA").resize((220, 310), keep_ratio=True, direction="north")
        frame.paste(img.rotate(25, expand=True), (56, 32), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="完美 ",
        usage="完美 <QQ号或@对方>",
        permission="anyone",
        description="完美",
        mode="表  情  包"
    )
    def perfect(self):
        frame = self.load_image("perfect/0.png")
        img = self.GetImage().convert("RGBA").resize((310, 460), keep_ratio=True, inside=True)
        frame.paste(img, (313, 64), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="关注 ",
        usage="关注 <QQ号或@对方>",
        permission="anyone",
        description="关注",
        mode="表  情  包"
    )
    def follow(self):
        img = self.GetImage().circle().resize((200, 200))

        userid = self.data.message
        if 'at' in userid:
            userid = CQCode(userid).get("qq")[0]
        userinfo = self.GetUserInfo(userid)

        ta = "女同" if userinfo.get('sex') == "female" else "男同"
        name = userinfo.get('nickname') or ta
        name_img = Text2Image.from_text(name, 60).to_image()
        follow_img = Text2Image.from_text("关注了你", 60, fill="grey").to_image()
        text_width = max(name_img.width, follow_img.width)
        if text_width >= 1000:
            return NAME_TOO_LONG

        frame = BuildImage.new("RGBA", (300 + text_width + 50, 300), (255, 255, 255, 0))
        frame.paste(img, (50, 50), alpha=True)
        frame.paste(name_img, (300, 135 - name_img.height), alpha=True)
        frame.paste(follow_img, (300, 145), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="这像画吗 ",
        usage="这像画吗 <QQ号或@对方>",
        permission="anyone",
        description="这像画吗",
        mode="表  情  包"
    )
    def paint(self):
        img = self.GetImage().convert("RGBA").resize((117, 135), keep_ratio=True)
        frame = self.load_image("paint/0.png")
        frame.paste(img.rotate(4, expand=True), (95, 107), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="震惊 ",
        usage="震惊 <QQ号或@对方>",
        permission="anyone",
        description="震惊",
        mode="表  情  包"
    )
    def shock(self):
        img = self.GetImage().convert("RGBA").resize((300, 300))
        frames: List[IMG] = []
        for i in range(30):
            frames.append(
                img.motion_blur(random.randint(-90, 90), random.randint(0, 50))
                .rotate(random.randint(-20, 20))
                .image
            )
        self.save_gif(frames, 0.01)

    @RegCmd(
        name="典中典 ",
        usage="典中典 <QQ号或@对方> <附加文字>",
        permission="anyone",
        description="典中典",
        mode="表  情  包"
    )
    def dianzhongdian(self):
        arg = self.data.args[2]
        if not arg:
            return self.client.msg().raw(REQUIRE_ARG)

        trans = self.utils.translator(arg)
        img = self.GetImage().convert("L").resize_width(500)
        text_img1 = BuildImage.new("RGBA", (500, 60))
        text_img2 = BuildImage.new("RGBA", (500, 35))
        try:
            text_img1.draw_text(
                (20, 0, text_img1.width - 20, text_img1.height),
                arg,
                max_fontsize=50,
                min_fontsize=25,
                fill="white",
            )
            text_img2.draw_text(
                (20, 0, text_img2.width - 20, text_img2.height),
                trans,
                max_fontsize=25,
                min_fontsize=10,
                fill="white",
            )
        except ValueError:
            return self.client.msg().raw(TEXT_TOO_LONG)

        frame = BuildImage.new("RGBA", (500, img.height + 100), "black")
        frame.paste(img, alpha=True)
        frame.paste(text_img1, (0, img.height), alpha=True)
        frame.paste(text_img2, (0, img.height + 60), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="哈哈镜 ",
        usage="哈哈镜 <QQ号或@对方>",
        permission="anyone",
        description="哈哈镜",
        mode="表  情  包"
    )
    def funny_mirror(self):
        img = self.GetImage().convert("RGBA").square().resize((500, 500))
        frames: List[IMG] = [img.image]
        coeffs = [0.01, 0.03, 0.05, 0.08, 0.12, 0.17, 0.23, 0.3, 0.4, 0.6]
        borders = [25, 52, 67, 83, 97, 108, 118, 128, 138, 148]
        for i in range(10):
            new_size = 500 - borders[i] * 2
            new_img = img.distort((coeffs[i], 0, 0, 0)).resize_canvas((new_size, new_size))
            frames.append(new_img.resize((500, 500)).image)
        frames.extend(frames[::-1])
        self.save_gif(frames, 0.05)

    @RegCmd(
        name="永远爱你 ",
        usage="永远爱你 <QQ号或@对方>",
        permission="anyone",
        description="永远爱你",
        mode="表  情  包"
    )
    def love_you(self):
        img = self.GetImage().convert("RGBA").square()
        frames: List[IMG] = []
        locs = [(68, 65, 70, 70), (63, 59, 80, 80)]
        for i in range(2):
            heart = self.load_image(f"love_you/{i}.png")
            frame = BuildImage.new("RGBA", heart.size, "white")
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), alpha=True).paste(heart, alpha=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.2)

    @RegCmd(
        name="对称 ",
        usage="对称 <QQ号或@对方>",
        permission="anyone",
        description="对称",
        mode="表  情  包"
    )
    def symmetric(self):
        arg = self.data.args[2]
        if arg not in ["上", "下", "左", "右"]:
            return self.client.msg().raw('可选方向：上、下、左、右！')
        img = self.GetImage().convert("RGBA").resize_width(500)
        img_w, img_h = img.size

        Mode = namedtuple(
            "Mode", ["method", "frame_size", "size1", "pos1", "size2", "pos2"]
        )
        modes: Dict[str, Mode] = {
            "left": Mode(
                Image.FLIP_LEFT_RIGHT,
                (img_w // 2 * 2, img_h),
                (0, 0, img_w // 2, img_h),
                (0, 0),
                (img_w // 2, 0, img_w // 2 * 2, img_h),
                (img_w // 2, 0),
            ),
            "right": Mode(
                Image.FLIP_LEFT_RIGHT,
                (img_w // 2 * 2, img_h),
                (img_w // 2, 0, img_w // 2 * 2, img_h),
                (img_w // 2, 0),
                (0, 0, img_w // 2, img_h),
                (0, 0),
            ),
            "top": Mode(
                Image.FLIP_TOP_BOTTOM,
                (img_w, img_h // 2 * 2),
                (0, 0, img_w, img_h // 2),
                (0, 0),
                (0, img_h // 2, img_w, img_h // 2 * 2),
                (0, img_h // 2),
            ),
            "bottom": Mode(
                Image.FLIP_TOP_BOTTOM,
                (img_w, img_h // 2 * 2),
                (0, img_h // 2, img_w, img_h // 2 * 2),
                (0, img_h // 2),
                (0, 0, img_w, img_h // 2),
                (0, 0),
            ),
        }

        mode = modes["left"]
        if arg == "右":
            mode = modes["right"]
        elif arg == "上":
            mode = modes["top"]
        elif arg == "下":
            mode = modes["bottom"]

        first = img
        second = img.transpose(mode.method)
        frame = BuildImage.new("RGBA", mode.frame_size)
        frame.paste(first.crop(mode.size1), mode.pos1)
        frame.paste(second.crop(mode.size2), mode.pos2)
        self.save_and_send(frame)

    @RegCmd(
        name="安全感 ",
        usage="安全感 <QQ号或@对方>",
        permission="anyone",
        description="安全感",
        mode="表  情  包"
    )
    def safe_sense(self):
        img = self.GetImage().convert("RGBA").resize((215, 343), keep_ratio=True)
        frame = self.load_image(f"safe_sense/0.png")
        frame.paste(img, (215, 135))

        text = "你给我的安全感\n远不及Ta的万分之一"
        try:
            frame.draw_text(
                (30, 0, 400, 130),
                text,
                max_fontsize=50,
                allow_wrap=True,
                lines_align="center",
            )
        except ValueError:
            return self.client.msg().raw(TEXT_TOO_LONG)
        self.save_and_send(frame)

    @RegCmd(
        name="永远喜欢 ",
        usage="永远喜欢 <QQ号或@对方>",
        permission="anyone",
        description="永远喜欢",
        mode="表  情  包"
    )
    def always_like(self):
        img = self.GetImage().convert("RGBA")
        userid = self.data.message
        if 'at' in userid:
            userid = CQCode(userid).get("qq")[0]

        name = self.GetUserInfo(userid).get('nickname')
        text = f"我永远喜欢{name}"

        frame = self.load_image(f"always_like/0.png")
        frame.paste(
            img.resize((350, 400), keep_ratio=True, inside=True), (25, 35), alpha=True
        )
        try:
            frame.draw_text(
                (20, 470, frame.width - 20, 570),
                text,
                max_fontsize=70,
                min_fontsize=30,
                weight="bold",
            )
        except ValueError:
            return self.client.msg().raw(NAME_TOO_LONG)

        def random_color():
            return random.choice(
                ["red", "darkorange", "gold", "darkgreen", "blue", "cyan", "purple"]
            )

        current_h = 400
        frame.paste(
            img.resize((350, 400), keep_ratio=True, inside=True),
            (10 + random.randint(0, 50), 20 + random.randint(0, 70)),
            alpha=True,
        )
        self.save_and_send(frame)

    @RegCmd(
        name="采访 ",
        usage="采访 <QQ号或@对方>",
        permission="anyone",
        description="采访",
        mode="表  情  包"
    )
    def interview(self):
        self_img = self.load_image("interview/huaji.png")
        user_img = self.GetImage()
        self_img = self_img.convert("RGBA").square().resize((124, 124))
        user_img = user_img.convert("RGBA").square().resize((124, 124))

        frame = BuildImage.new("RGBA", (600, 310), "white")
        microphone = self.load_image("interview/microphone.png")
        frame.paste(microphone, (330, 103), alpha=True)
        frame.paste(self_img, (419, 40), alpha=True)
        frame.paste(user_img, (57, 40), alpha=True)
        try:
            frame.draw_text(
                (20, 200, 580, 310), "采访大佬经验", max_fontsize=50, min_fontsize=20
            )
        except ValueError:
            return self.client.msg().raw(TEXT_TOO_LONG)
        self.save_and_send(frame)

    @RegCmd(
        name="打拳 ",
        usage="打拳 <QQ号或@对方>",
        permission="anyone",
        description="打拳",
        mode="表  情  包"
    )
    def punch(self):
        img = self.GetImage().convert("RGBA").square().resize((260, 260))
        frames: List[IMG] = []
        # fmt: off
        locs = [
            (-50, 20), (-40, 10), (-30, 0), (-20, -10), (-10, -10), (0, 0),
            (10, 10), (20, 20), (10, 10), (0, 0), (-10, -10), (10, 0), (-30, 10)
        ]
        # fmt: on
        for i in range(13):
            fist = self.load_image(f"punch/{i}.png")
            frame = BuildImage.new("RGBA", fist.size, "white")
            x, y = locs[i]
            frame.paste(img, (x, y - 15), alpha=True).paste(fist, alpha=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.03)

    @RegCmd(
        name="群青 ",
        usage="群青 <QQ号或@对方>",
        permission="anyone",
        description="群青",
        mode="表  情  包"
    )
    def cyan(self):
        color = (78, 114, 184)
        frame = self.GetImage().convert("RGB").square().resize((500, 500)).color_mask(color)
        frame.draw_text(
            (400, 40, 480, 280),
            "群\n青",
            max_fontsize=80,
            weight="bold",
            fill="white",
            stroke_ratio=0.025,
            stroke_fill=color,
        ).draw_text(
            (200, 270, 480, 350),
            "YOASOBI",
            halign="right",
            max_fontsize=40,
            fill="white",
            stroke_ratio=0.06,
            stroke_fill=color,
        )
        self.save_and_send(frame)

    @RegCmd(
        name="捣 ",
        usage="捣 <QQ号或@对方>",
        permission="anyone",
        description="捣",
        mode="表  情  包"
    )
    def pound(self):
        img = self.GetImage().convert("RGBA").square()
        # fmt: off
        locs = [
            (135, 240, 138, 47), (135, 240, 138, 47), (150, 190, 105, 95), (150, 190, 105, 95),
            (148, 188, 106, 98), (146, 196, 110, 88), (145, 223, 112, 61), (145, 223, 112, 61)
        ]
        # fmt: on
        frames: List[IMG] = []
        for i in range(8):
            frame = self.load_image(f"pound/{i}.png")
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.05)

    @RegCmd(
        name="捶 ",
        usage="捶 <QQ号或@对方>",
        permission="anyone",
        description="捶某人的头像",
        mode="表  情  包"
    )
    def thump(self):
        img = self.GetImage().convert("RGBA").square()
        # fmt: off
        locs = [(65, 128, 77, 72), (67, 128, 73, 72), (54, 139, 94, 61), (57, 135, 86, 65)]
        # fmt: on
        frames: List[IMG] = []
        for i in range(4):
            frame = self.load_image(f"thump/{i}.png")
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.04)

    @RegCmd(
        name="需要 ",
        usage="需要 <QQ号或@对方>",
        permission="anyone",
        description="需要",
        mode="表  情  包"
    )
    def need(self):
        img = self.GetImage().convert("RGBA").square().resize((115, 115))
        frame = self.load_image("need/0.png")
        frame.paste(img, (327, 232), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="捂脸 ",
        usage="捂脸 <QQ号或@对方>",
        permission="anyone",
        description="捂脸",
        mode="表  情  包"
    )
    def cover_face(self):
        points = ((15, 15), (448, 0), (445, 456), (0, 465))
        img = self.GetImage().convert("RGBA").square().resize((450, 450)).perspective(points)
        frame = self.load_image("cover_face/0.png")
        frame.paste(img, (120, 150), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="敲 ",
        usage="敲 <QQ号或@对方>",
        permission="anyone",
        description="敲",
        mode="表  情  包"
    )
    def knock(self):
        img = self.GetImage().convert("RGBA").square()
        # fmt: off
        locs = [(60, 308, 210, 195), (60, 308, 210, 198), (45, 330, 250, 172), (58, 320, 218, 180),
                (60, 310, 215, 193), (40, 320, 250, 285), (48, 308, 226, 192), (51, 301, 223, 200)]
        # fmt: on
        frames: List[IMG] = []
        for i in range(8):
            frame = self.load_image(f"knock/{i}.png")
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.04)

    @RegCmd(
        name="垃圾 ",
        usage="垃圾 <QQ号或@对方>",
        permission="anyone",
        description="垃圾",
        mode="表  情  包"
    )
    def garbage(self):
        img = self.GetImage().convert("RGBA").square().resize((79, 79))
        # fmt: off
        locs = (
                [] + [(39, 40)] * 3 + [(39, 30)] * 2 + [(39, 32)] * 10
                + [(39, 30), (39, 27), (39, 32), (37, 49), (37, 64),
                   (37, 67), (37, 67), (39, 69), (37, 70), (37, 70)]
        )
        # fmt: on
        frames: List[IMG] = []
        for i in range(25):
            frame = self.load_image(f"garbage/{i}.png")
            frame.paste(img, locs[i], below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.04)

    @RegCmd(
        name="为什么@我 ",
        usage="为什么@我 <QQ号或@对方>",
        permission="anyone",
        description="为什么@我",
        mode="表  情  包"
    )
    def whyatme(self):
        img = self.GetImage().convert("RGBA").resize((265, 265), keep_ratio=True)
        frame = self.load_image("whyatme/0.png")
        frame.paste(img, (42, 13), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="像样的亲亲 ",
        usage="像样的亲亲 <QQ号或@对方>",
        permission="anyone",
        description="像样的亲亲",
        mode="表  情  包"
    )
    def decent_kiss(self):
        img = self.GetImage().convert("RGBA").resize((589, 340), keep_ratio=True)
        frame = self.load_image("decent_kiss/0.png")
        frame.paste(img, (0, 91), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="啾啾 ",
        usage="啾啾 <QQ号或@对方>",
        permission="anyone",
        description="啾啾",
        mode="表  情  包"
    )
    def jiujiu(self):
        img = self.GetImage().convert("RGBA").resize((75, 51), keep_ratio=True)
        frames: List[IMG] = []
        for i in range(8):
            frame = self.load_image(f"jiujiu/{i}.png")
            frame.paste(img, below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.06)

    @RegCmd(
        name="吸 ",
        usage="吸 <QQ号或@对方>",
        permission="anyone",
        description="吸",
        mode="表  情  包"
    )
    def suck(self):
        img = self.GetImage().convert("RGBA").square()
        # fmt: off
        locs = [(82, 100, 130, 119), (82, 94, 126, 125), (82, 120, 128, 99), (81, 164, 132, 55),
                (79, 163, 132, 55), (82, 140, 127, 79), (83, 152, 125, 67), (75, 157, 140, 62),
                (72, 165, 144, 54), (80, 132, 128, 87), (81, 127, 127, 92), (79, 111, 132, 108)]
        # fmt: on
        frames: List[IMG] = []
        for i in range(12):
            bg = self.load_image(f"suck/{i}.png")
            frame = BuildImage.new("RGBA", bg.size, "white")
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), alpha=True).paste(bg, alpha=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.08)

    @RegCmd(
        name="锤 ",
        usage="锤 <QQ号或@对方>",
        permission="anyone",
        description="锤",
        mode="表  情  包"
    )
    def hammer(self):
        img = self.GetImage().convert("RGBA").square()
        # fmt: off
        locs = [(62, 143, 158, 113), (52, 177, 173, 105), (42, 192, 192, 92), (46, 182, 184, 100),
                (54, 169, 174, 110), (69, 128, 144, 135), (65, 130, 152, 124)]
        # fmt: on
        frames: List[IMG] = []
        for i in range(7):
            frame = self.load_image(f"hammer/{i}.png")
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.07)

    @RegCmd(
        name="紧贴 ",
        usage="紧贴 <QQ号或@对方>",
        permission="anyone",
        description="紧贴",
        mode="表  情  包"
    )
    def tightly(self):
        img = self.GetImage().convert("RGBA").resize((640, 400), keep_ratio=True)
        # fmt: off
        locs = [(39, 169, 267, 141), (40, 167, 264, 143), (38, 174, 270, 135), (40, 167, 264, 143),
                (38, 174, 270, 135),
                (40, 167, 264, 143), (38, 174, 270, 135), (40, 167, 264, 143), (38, 174, 270, 135),
                (28, 176, 293, 134),
                (5, 215, 333, 96), (10, 210, 321, 102), (3, 210, 330, 104), (4, 210, 328, 102), (4, 212, 328, 100),
                (4, 212, 328, 100), (4, 212, 328, 100), (4, 212, 328, 100), (4, 212, 328, 100), (29, 195, 285, 120)]
        # fmt: on
        frames: List[IMG] = []
        for i in range(20):
            frame = self.load_image(f"tightly/{i}.png")
            x, y, w, h = locs[i]
            frame.paste(img.resize((w, h)), (x, y), below=True)
            frames.append(frame.image)
        self.save_gif(frames, 0.08)

    @RegCmd(
        name="注意力涣散 ",
        usage="注意力涣散 <QQ号或@对方>",
        permission="anyone",
        description="注意力涣散",
        mode="表  情  包"
    )
    def distracted(self):
        img = self.GetImage().convert("RGBA").square().resize((500, 500))
        frame = self.load_image("distracted/1.png")
        label = self.load_image("distracted/0.png")
        frame.paste(img, below=True).paste(label, (140, 320), alpha=True)
        self.save_and_send(frame)

    @RegCmd(
        name="结婚申请 ",
        usage="结婚申请 <QQ号或@对方>",
        permission="anyone",
        description="结婚申请",
        mode="表  情  包"
    )
    def marriage(self):
        img = self.GetImage().convert("RGBA").resize_height(1080)
        img_w, img_h = img.size
        if img_w > 1500:
            img_w = 1500
        elif img_w < 800:
            img_h = int(img_h * img_w / 800)
            img_w = 800
        frame = img.resize_canvas((img_w, img_h)).resize_height(1080)
        left = self.load_image("marriage/0.png")
        right = self.load_image("marriage/1.png")
        frame.paste(left, alpha=True).paste(
            right, (frame.width - right.width, 0), alpha=True
        )
        self.save_and_send(frame)

    @RegCmd(
        name="想什么 ",
        usage="想什么 <QQ号或@对方>",
        permission="anyone",
        description="想什么",
        mode="表  情  包"
    )
    def thinkwhat(self):
        frame = self.load_image("thinkwhat/0.png")

        def make(img: BuildImage) -> BuildImage:
            return frame.copy().paste(
                img.resize((534, 493), keep_ratio=True), (530, 0), below=True
            )

        return self.make_jpg_or_gif(self.GetImage(), make)

    @RegCmd(
        name="阿尼亚喜欢 ",
        usage="阿尼亚喜欢 <QQ号或@对方>",
        permission="anyone",
        description="阿尼亚喜欢",
        mode="表  情  包"
    )
    def anyasuki(self):
        frame = self.load_image("anyasuki/0.png")
        try:
            frame.draw_text(
                (2, frame.height - 50, frame.width - 20, frame.height),
                "喜欢这个",
                max_fontsize=40,
                fill="white",
                stroke_fill="black",
                stroke_ratio=0.06,
            )
        except ValueError:
            return self.client.msg().raw(TEXT_TOO_LONG)

        def make(img: BuildImage) -> BuildImage:
            return frame.copy().paste(
                img.resize((305, 235), keep_ratio=True), (106, 72), below=True
            )

        return self.make_jpg_or_gif(self.GetImage(), make)

    @RegCmd(
        name="远离 ",
        usage="远离 <QQ号或@对方>",
        permission="anyone",
        description="远离",
        mode="表  情  包"
    )
    def keepaway(self):
        imgs = [self.GetImage()]

        def trans(img: BuildImage, n: int) -> BuildImage:
            img = img.convert("RGBA").square().resize((100, 100))
            if n < 4:
                return img.rotate(n * 90)
            else:
                return img.transpose(Image.FLIP_LEFT_RIGHT).rotate((n - 4) * 90)

        def paste(img: BuildImage):
            nonlocal count
            y = 90 if count < 4 else 190
            frame.paste(img, ((count % 4) * 100, y))
            count += 1

        frame = BuildImage.new("RGB", (400, 290), "white")
        frame.draw_text(
            (10, 10, 220, 80), "如何提高社交质量 : \n远离以下头像的人", max_fontsize=21, halign="left"
        )
        count = 0
        num_per_user = 8 // len(imgs)
        for img in imgs:
            for n in range(num_per_user):
                paste(trans(img, n))
        num_left = 8 - num_per_user * len(imgs)
        for n in range(num_left):
            paste(trans(imgs[-1], n + num_per_user))

        self.save_and_send(frame)

    @RegCmd(
        name="小画家 ",
        usage="小画家 <QQ号或@对方>",
        permission="anyone",
        description="小画家",
        mode="表  情  包"
    )
    def painter(self):
        img = self.GetImage().convert("RGBA").resize((240, 345), keep_ratio=True)
        frame = self.load_image("painter/0.png")
        frame.paste(img, (125, 91), below=True)
        self.save_and_send(frame)

    @RegCmd(
        name="救命啊 ",
        usage="救命啊 <QQ号或@对方>",
        permission="anyone",
        description="重复 救命啊！",
        mode="表  情  包"
    )
    def repeat(self):
        users = [self.GetImage()]
        userid = self.data.message
        if 'at' in userid:
            userid = CQCode(userid).get("qq")[0]

        username = self.GetUserInfo(userid).get('nickname')

        def single_msg(img: BuildImage) -> BuildImage:
            user_img = img.convert("RGBA").circle().resize((100, 100))
            user_name_img = Text2Image.from_text(f"{username}", 40).to_image()
            time = datetime.now().strftime("%H:%M")
            time_img = Text2Image.from_text(time, 40, fill="gray").to_image()
            bg = BuildImage.new("RGB", (1079, 200), (248, 249, 251, 255))
            bg.paste(user_img, (50, 50), alpha=True)
            bg.paste(user_name_img, (175, 45), alpha=True)
            bg.paste(time_img, (200 + user_name_img.width, 50), alpha=True)
            bg.paste(text_img, (175, 100), alpha=True)
            return bg

        text = "救命啊"
        text_img = Text2Image.from_text(text, 50).to_image()

        msg_img = BuildImage.new("RGB", (1079, 1000))
        for i in range(5):
            index = i % len(users)
            msg_img.paste(single_msg(users[index]), (0, 200 * i))
        msg_img_twice = BuildImage.new("RGB", (msg_img.width, msg_img.height * 2))
        msg_img_twice.paste(msg_img).paste(msg_img, (0, msg_img.height))

        input_img = self.load_image("repeat/0.jpg")
        self_img = self.GetImage({'message': str(self.data.se.get('user_id'))}).convert("RGBA").circle().resize(
            (75, 75))
        input_img.paste(self_img, (15, 40), alpha=True)

        frames: List[IMG] = []
        for i in range(50):
            frame = BuildImage.new("RGB", (1079, 1192), "white")
            frame.paste(msg_img_twice, (0, -20 * i))
            frame.paste(input_img, (0, 1000))
            frames.append(frame.image)

        self.save_gif(frames, 0.08)
