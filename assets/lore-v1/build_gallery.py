"""Build a portable local gallery from the art manifest; no dependencies."""

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
manifest = json.loads((ROOT / "manifest.json").read_text())
labels = {
    "location": "Локации",
    "npc": "Персонажи",
    "mob": "Обитатели и противники",
    "class": "Классы",
    "item": "Снаряжение",
    "skill": "Умения",
}
worlds = {"teren": "Терен", "sairan": "Сайран", "shared": "Общее"}
sections = []
ready = 0
for category, label in labels.items():
    cards = []
    for asset in manifest["assets"]:
        if asset["category"] != category:
            continue
        name = html.escape(asset["name"])
        path = html.escape(asset["file"], quote=True)
        exists = (ROOT / asset["file"]).is_file()
        ready += int(exists)
        preview = (
            f'<a href="{path}" target="_blank"><img src="{path}" alt="{name}" loading="lazy"></a>'
            if exists else '<div class="pending">Изображение готовится</div>'
        )
        level = f' · уровень {asset["level"]}' if "level" in asset else ""
        class_names = {"warrior": "Воин", "mage": "Маг", "rogue": "Разбойник"}
        class_label = class_names.get(asset["id"].split("-")[1], "") if category == "skill" else ""
        if class_label:
            level += " · " + class_label
        cards.append(
            f'<article class="{category}">{preview}<div class="caption"><h3>{name}</h3>'
            f'<p>{worlds[asset["world"]]}{level}</p>'
            f'<details><summary>Промпт</summary><p>{html.escape(asset["prompt"])}</p></details>'
            '</div></article>'
        )
    sections.append(f'<section id="{category}"><h2>{label}</h2><div class="grid">{"".join(cards)}</div></section>')

navigation = ''.join(f'<a href="#{key}">{label}</a>' for key, label in labels.items())
page = '''<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Терен и Сайран — художественный каталог</title>
<style>
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#eee8dd;color:#302a23;font:17px/1.5 Georgia,serif}
header,main,footer{max-width:1440px;margin:auto;padding:32px}header{padding-top:56px}h1{font-size:clamp(32px,5vw,58px);line-height:1.1;margin:8px 0 20px}h2{font-size:30px;margin:0 0 22px}h3{font-size:20px;margin:0}
.eyebrow{font:12px/1.4 system-ui;letter-spacing:.18em;text-transform:uppercase;color:#79624a}header p{max-width:820px}nav{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px}a{color:#714529}nav a{padding:8px 14px;border:1px solid #cabb9f;text-decoration:none;border-radius:3px}section{padding:20px 0 42px;scroll-margin-top:20px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}#location .grid{grid-template-columns:repeat(2,minmax(0,1fr))}#skill .grid{grid-template-columns:repeat(5,minmax(0,1fr))}article{background:#faf7f0;border:1px solid #d1c6b6;overflow:hidden;border-radius:4px}img{display:block;width:100%;aspect-ratio:1;object-fit:contain;background:#262522}.location img{aspect-ratio:16/9}.caption{padding:18px}.caption>p{margin:5px 0;color:#766650;font:13px/1.5 system-ui}details{font:12px/1.6 system-ui;margin-top:16px}details p{overflow-wrap:anywhere}summary{cursor:pointer;color:#79624a}.pending{display:grid;place-items:center;aspect-ratio:1;color:#79624a;background:#e4ddcf}.location .pending{aspect-ratio:16/9}footer{border-top:1px solid #cabb9f;font-size:14px}
@media(max-width:760px){header,main,footer{padding:20px}.grid,#location .grid{grid-template-columns:1fr}#skill .grid{grid-template-columns:repeat(2,minmax(0,1fr))}h1{font-size:36px}}
</style><header><div class="eyebrow">Первый художественный вариант · 27 сентября 2026</div>
<h1>Терен и Сайран</h1><p>Два самостоятельных мира, знакомые очертания и разные судьбы. Реалистичное средневековое фэнтези для стартовых уровней 1–7.</p>
'''
page += f'<p>Готово изображений: <strong>{ready} / {len(manifest["assets"])}</strong>. Нажмите на изображение, чтобы открыть оригинал.</p>'
page += f'<nav>{navigation}</nav></header><main>{"".join(sections)}</main>'
page += '<footer>Новые имена и истории — авторский вариант. <a href="../../specifications/lore/README.md">Полный лор</a> · <a href="manifest.json">Реестр и промпты</a>. Создано встроенным image_gen. Изображения пока не подключены к игре.</footer></html>'
(ROOT / "index.html").write_text(page)
print(f'Gallery: {ready}/{len(manifest["assets"])} images')
