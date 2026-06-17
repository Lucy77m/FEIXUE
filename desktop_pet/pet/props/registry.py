# author: bdth
# email: 2074055628@qq.com
# 装扮注册表 哪个道具穿身上 哪个撒周围 一处登记

from __future__ import annotations

from desktop_pet.pet.props.activities import draw_coffee, draw_book, draw_headphones, draw_fishing, draw_gaming, draw_telescope, draw_sherlock
from desktop_pet.pet.props.effects import draw_confetti, draw_raincloud, draw_sweat, draw_void, draw_clone, draw_meteor, draw_sprout, draw_yarn, draw_magic, draw_crystalball, draw_fishmoon, draw_butterfly, draw_fireworks
from desktop_pet.pet.props.food import draw_icecream, draw_bubbletea, draw_tanghulu, draw_watermelon, draw_lollipop, draw_popcorn, draw_donut, draw_soda, draw_corn, draw_sushi, draw_popsicle, draw_cottoncandy, draw_burger, draw_noodles, draw_tea, draw_marshmallow, draw_sweetpotato, draw_cupcake, draw_pizza
from desktop_pet.pet.props.toys import draw_bubbles, draw_balloon, draw_paperplane, draw_kite, draw_yoyo, draw_blocks, draw_pinwheel, draw_rubik, draw_ringtoss, draw_spintop, draw_cards, draw_matryoshka, draw_frisbee, draw_paperboat, draw_darts, draw_snowglobe, draw_piggybank, draw_sheep, draw_crane, draw_lantern
from desktop_pet.pet.props.crafts import draw_camera, draw_guitar, draw_harmonica, draw_trumpet, draw_piano, draw_painting, draw_calligraphy, draw_knitting, draw_phone, draw_watering, draw_dandelion, draw_bouquet


# 装扮注册表 worn 穿身上 ambient 撒周围 二者互斥
COSTUME_LAYERS = {
    "sherlock": (draw_sherlock, None),
    "coffee": (draw_coffee, None),
    "book": (draw_book, None),
    "headphones": (draw_headphones, None),
    "fishing": (draw_fishing, None),
    "gaming": (draw_gaming, None),
    "telescope": (draw_telescope, None),
    "party": (None, draw_confetti),
    "raincloud": (None, draw_raincloud),
    "sweat": (None, draw_sweat),
    "void": (None, draw_void),
    "clone": (None, draw_clone),
    "meteor": (None, draw_meteor),
    "sprout": (None, draw_sprout),
    "yarn": (None, draw_yarn),
    "bubbles": (None, draw_bubbles),
    "balloon": (None, draw_balloon),
    "icecream": (None, draw_icecream),
    "paperplane": (None, draw_paperplane),
    "kite": (None, draw_kite),
    "camera": (draw_camera, None),
    "bubbletea": (None, draw_bubbletea),
    "tanghulu": (None, draw_tanghulu),
    "dandelion": (None, draw_dandelion),
    "guitar": (draw_guitar, None),
    "watermelon": (draw_watermelon, None),
    "fireworks": (None, draw_fireworks),
    "yoyo": (None, draw_yoyo),
    "painting": (None, draw_painting),
    "watering": (None, draw_watering),
    "blocks": (None, draw_blocks),
    "lollipop": (None, draw_lollipop),
    "popcorn": (None, draw_popcorn),
    "pinwheel": (None, draw_pinwheel),
    "donut": (None, draw_donut),
    "soda": (None, draw_soda),
    "corn": (draw_corn, None),
    "sushi": (None, draw_sushi),
    "rubik": (None, draw_rubik),
    "magic": (None, draw_magic),
    "knitting": (None, draw_knitting),
    "phone": (None, draw_phone),
    "harmonica": (None, draw_harmonica),
    "popsicle": (None, draw_popsicle),
    "butterfly": (None, draw_butterfly),
    "fishmoon": (None, draw_fishmoon),
    "ringtoss": (None, draw_ringtoss),
    "lantern": (None, draw_lantern),
    "cottoncandy": (None, draw_cottoncandy),
    "burger": (None, draw_burger),
    "noodles": (None, draw_noodles),
    "tea": (None, draw_tea),
    "marshmallow": (None, draw_marshmallow),
    "calligraphy": (None, draw_calligraphy),
    "darts": (None, draw_darts),
    "paperboat": (None, draw_paperboat),
    "pizza": (None, draw_pizza),
    "spintop": (None, draw_spintop),
    "crane": (None, draw_crane),
    "piano": (None, draw_piano),
    "piggybank": (None, draw_piggybank),
    "crystalball": (None, draw_crystalball),
    "cards": (None, draw_cards),
    "matryoshka": (None, draw_matryoshka),
    "sheep": (None, draw_sheep),
    "bouquet": (None, draw_bouquet),
    "sweetpotato": (None, draw_sweetpotato),
    "trumpet": (None, draw_trumpet),
    "frisbee": (None, draw_frisbee),
    "cupcake": (None, draw_cupcake),
    "snowglobe": (None, draw_snowglobe),
}
COSTUMES = frozenset(COSTUME_LAYERS)
WORN_COSTUMES = frozenset(name for name, (worn, _ambient) in COSTUME_LAYERS.items() if worn)

# 举着东西的道具在底部握点画只圆小手防浮空 gx gy 是 bw bh 系数
# 只登记该有只手攥着且当前没画手的
GRIP = {
    # 食物
    "icecream": (0.30, 0.32), "bubbletea": (0.30, 0.25), "tanghulu": (0.16, 0.29),
    "lollipop": (0.255, 0.25), "popcorn": (0.30, 0.27), "donut": (0.30, 0.16),
    "soda": (0.30, 0.25), "popsicle": (0.30, 0.30), "cottoncandy": (0.30, 0.27),
    "burger": (0.30, 0.17), "noodles": (0.28, 0.28), "marshmallow": (0.40, 0.10),
    "sweetpotato": (0.22, 0.11), "cupcake": (0.30, 0.25), "pizza": (0.28, 0.24),
    "watermelon": (0.28, 0.27), "corn": (0.20, 0.23),
    # 玩具 balloon kite yoyo lantern 代码里已定握点在那儿补手 其余举把柄底座
    "balloon": (0.22, 0.20), "kite": (0.20, 0.12), "yoyo": (0.28, 0.04),
    "lantern": (0.18, 0.06), "pinwheel": (0.31, 0.28), "rubik": (0.30, 0.13),
    "cards": (0.30, 0.14), "snowglobe": (0.30, 0.21), "crane": (0.30, 0.13),
    # 手作只取举着的 手机蒲公英捧花 浇花书法等手位偏头暂不加
    "phone": (0.30, 0.16), "dandelion": (0.26, 0.28), "bouquet": (0.30, 0.27),
}
