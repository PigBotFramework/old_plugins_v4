from google.protobuf.json_format import MessageToDict
from dynamicadaptor.DynamicConversion import formate_message
from bilirpc.api import get_dy_detail
import asyncio
from minidynamicrender.Core import DyRender 

async def sample1():
    dynamic_grpc = await get_dy_detail("746530608345251842")
    dynamic: dict = MessageToDict(dynamic_grpc[0])
    dynamic_formate = formate_message("grpc", dynamic)
    render = DyRender()
    # DyRender 实例化时可以传两个参数
    #1. data_path: {str} 为静态文件所在的位置，当data_path内不存在Static目录，则会自动解压自带的Static到data_path内
    # 2.font_path: {str/dic}当font_path为str类型的时候必须为字体的路径，路径不存在的话会使用默认的字体
    # 不建议使用传dict的方法修改字体
    # 当font_path为dict的时候必须为如以下所示的dict:
    """
    {
     text: str
     extra_text: str
     emoji: str
    }
    三个都必须是字体的路径，text为文本主体的字体路径，extra_text为备选字体的路径，emoji为emoji字体的路径，
    
    注意！！！
    
    每款emoji字体的字体大小都有固定值，如果修改了emoji字体必须同时修改emoji字体的字体大小
    
    """
    result = await render.dyn_render(dynamic_formate)
    result.show()
    
asyncio.run(sample1())