# Génère banniere.jpg à partir de la dernière actualité publiée sur mecalab.be
# Lancé automatiquement chaque matin par GitHub (voir .github/workflows/banniere.yml)
import glob, html, re, sys
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

SITE = 'https://www.mecalab.be'
LISTES = ['/fr/news/cat1_actualites', '/fr/news/cat3_realisations']
UA = {'User-Agent': 'Mozilla/5.0 (signature Mecalab)'}
MOIS = 'janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre'

LORA = 'fonts/Lora.ttf'
POP_R = 'fonts/Poppins-Regular.ttf'
POP_M = 'fonts/Poppins-Medium.ttf'

S = 2
W, H = 600 * S, 280 * S
BAND = 56 * S
NAVY = (28, 37, 65)
BLUE = (42, 124, 185)


def get(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


def derniere_news():
    articles = {}
    categorie = {}
    for liste in LISTES:
        for m in re.finditer(r'/fr/news/(\d+)_([a-z0-9\-]+)', get(SITE + liste)):
            articles[int(m.group(1))] = f'{SITE}/fr/news/{m.group(1)}_{m.group(2)}'
            if 'realisations' in liste:
                categorie[int(m.group(1))] = 'realisation'
    if not articles:
        raise RuntimeError('aucune actualité trouvée')
    nid = max(articles)
    page = get(articles[nid])
    titre = None
    for pat in (r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title',
                r'<h1[^>]*>(.*?)</h1>',
                r'<title[^>]*>(.*?)</title>'):
        m = re.search(pat, page, re.S | re.I)
        if m:
            titre = re.sub(r'<[^>]+>', '', html.unescape(m.group(1))).strip()
            titre = re.sub(r'\s*[|\-–]\s*Mecalab\s*$', '', titre, flags=re.I)
            if titre:
                break
    texte = re.sub(r'<[^>]+>', ' ', page)
    d = re.search(rf'\b(\d{{1,2}})\s+({MOIS})\s+(20\d\d)\b', texte, re.I)
    date = f'{d.group(1)} {d.group(2).lower()} {d.group(3)}' if d else None
    if not date:
        n = re.search(r'\b(\d{1,2})[/.](\d{1,2})[/.](20\d\d)\b', texte)
        if n and 1 <= int(n.group(2)) <= 12:
            noms = ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre']
            date = f'{int(n.group(1))} {noms[int(n.group(2))-1]} {n.group(3)}'
    return nid, titre or 'Découvrez nos dernières actualités', date, categorie.get(nid, 'actualite')


def font(path, size, weight=None):
    f = ImageFont.truetype(path, size)
    if weight:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def couper(d, texte, f, largeur):
    lignes, cur = [], ''
    for mot in texte.split():
        essai = (cur + ' ' + mot).strip()
        if d.textlength(essai, font=f) <= largeur:
            cur = essai
        else:
            if cur:
                lignes.append(cur)
            cur = mot
    if cur:
        lignes.append(cur)
    return lignes


def generer(nid, titre, date, cat='actualite'):
    photos = sorted(glob.glob('photo-*.jpg') + glob.glob('photo-*.jpeg') + glob.glob('photo-*.png'))
    ph_h = H - BAND
    img = Image.new('RGB', (W, H), NAVY)
    if photos:  # une photo différente selon la news
        ph = ImageOps.exif_transpose(Image.open(photos[nid % len(photos)])).convert('RGB')
        ratio = W / ph_h
        if ph.width / ph.height > ratio:
            cw = int(ph.height * ratio); x0 = (ph.width - cw) // 2
            ph = ph.crop((x0, 0, x0 + cw, ph.height))
        else:
            ch = int(ph.width / ratio); y0 = int((ph.height - ch) * 0.45)
            ph = ph.crop((0, y0, ph.width, y0 + ch))
        img.paste(ph.resize((W, ph_h), Image.LANCZOS), (0, 0))

    # voile bleu nuit : dense à gauche, léger à droite
    x = np.linspace(0, 1, W)
    a = np.tile(0.92 - 0.66 * np.clip((x - 0.18) / 0.42, 0, 1), (ph_h, 1))[..., None]
    base = np.array(img.crop((0, 0, W, ph_h))).astype(float)
    img.paste(Image.fromarray((base * (1 - a) + np.array(NAVY, float) * a).astype('uint8')), (0, 0))
    d = ImageDraw.Draw(img)

    # logo dans un cercle blanc
    D, cx, cy = 76 * S, 22 * S, 14 * S
    m = Image.new('L', (D * 4, D * 4), 0)
    ImageDraw.Draw(m).ellipse((0, 0, D * 4 - 1, D * 4 - 1), fill=255)
    img.paste(Image.new('RGB', (D, D), 'white'), (cx, cy), m.resize((D, D), Image.LANCZOS))
    logo = Image.open('logo-mecalab.png').convert('RGBA')
    lw = int(D * 0.80)
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    img.paste(logo, (cx + (D - lw) // 2, cy + (D - logo.height) // 2), logo)

    # titre serif (taille adaptée à la longueur)
    tx, larg = 24 * S, 350 * S
    for taille in (26, 23, 20, 18, 16):
        tf = font(LORA, taille * S, 600)
        lignes = couper(d, titre, tf, larg)
        if len(lignes) <= 3:
            break
    lignes = lignes[:3]
    pas = int(taille * 1.22) * S
    y_bas = 176 * S
    y = y_bas - pas * (len(lignes) - 1)
    for l in lignes:
        d.text((tx, y), l, font=tf, fill='white', anchor='ls')
        y += pas
    d.line((tx, 188 * S, tx + 160 * S, 188 * S), fill=(200, 205, 215), width=S)
    sf = font(POP_R, 11 * S)
    xx = tx
    for c in ('NOTRE DERNIÈRE RÉALISATION' if cat == 'realisation' else 'NOTRE DERNIÈRE ACTUALITÉ'):
        d.text((xx, 208 * S), c, font=sf, fill='white', anchor='ls')
        xx += d.textlength(c, font=sf) + 3.2 * S

    # bande bleue + icônes
    by = H - BAND
    d.rectangle((0, by, W, H), fill=BLUE)
    bf = font(POP_M, 12 * S)
    my = by + BAND // 2
    w = 2 * S
    if date:
        x0, y0 = 24 * S, my - 11 * S
        d.rounded_rectangle((x0, y0 + 3*S, x0 + 20*S, y0 + 21*S), radius=3*S, outline='white', width=w)
        d.line((x0, y0 + 8*S, x0 + 20*S, y0 + 8*S), fill='white', width=w)
        for k in (5, 15):
            d.line((x0 + k*S, y0, x0 + k*S, y0 + 5*S), fill='white', width=w)
        for r in range(2):
            for c in range(3):
                px, py = x0 + (4 + c*5)*S, y0 + (11 + r*5)*S
                d.rectangle((px, py, px + 2*S, py + 2*S), fill='white')
        d.text((52 * S, my), date.capitalize(), font=bf, fill='white', anchor='lm')
    else:
        lib = 'Découvrir le projet' if cat == 'realisation' else 'Lire l’actualité'
        d.text((24 * S, my), lib, font=bf, fill='white', anchor='lm')
        ax = 24 * S + d.textlength(lib, font=bf) + 10 * S
        d.line((ax, my, ax + 16 * S, my), fill='white', width=2 * S)
        d.polygon([(ax + 18 * S, my), (ax + 11 * S, my - 5 * S), (ax + 11 * S, my + 5 * S)], fill='white')
    d.text((W // 2, my), 'www.mecalab.be', font=bf, fill='white', anchor='mm')
    loc = 'Villers-le-Bouillet'
    lx = W - 24 * S - d.textlength(loc, font=bf)
    x0, y0 = lx - 28 * S, my - 11 * S
    d.ellipse((x0 + 2*S, y0, x0 + 18*S, y0 + 16*S), outline='white', width=w)
    d.polygon([(x0 + 4*S, y0 + 12*S), (x0 + 16*S, y0 + 12*S), (x0 + 10*S, y0 + 22*S)], fill='white')
    d.ellipse((x0 + 3*S + 1, y0 + S + 1, x0 + 17*S - 1, y0 + 15*S - 1), fill=BLUE)
    d.ellipse((x0 + 7*S, y0 + 5*S, x0 + 13*S, y0 + 11*S), outline='white', width=w)
    d.text((lx, my), loc, font=bf, fill='white', anchor='lm')

    img.save('banniere.jpg', quality=86, optimize=True, progressive=True)


if __name__ == '__main__':
    if len(sys.argv) > 1:          # test manuel : python generer_banniere.py "Titre" "16 juillet 2026"
        generer(1, sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
        sys.exit(0)
    try:
        nid, titre, date, cat = derniere_news()
    except Exception as e:          # site injoignable : on garde l'ancienne bannière
        print('Pas de mise à jour :', e)
        sys.exit(0)
    print('Dernière news :', nid, cat, titre, date)
    generer(nid, titre, date, cat)
