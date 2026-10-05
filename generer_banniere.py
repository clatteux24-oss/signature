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

# Police du site mecalab.be : Source Sans 3 (ex-Source Sans Pro)
TITRE = 'fonts/SourceSans3-700.ttf'
SS_R = 'fonts/SourceSans3-400.ttf'
SS_SB = 'fonts/SourceSans3-600.ttf'

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
    images = {}
    for liste in LISTES:
        page_liste = get(SITE + liste)
        for m in re.finditer(r'/fr/news/(\d+)_([a-z0-9\-]+)', page_liste):
            articles[int(m.group(1))] = f'{SITE}/fr/news/{m.group(1)}_{m.group(2)}'
            if 'realisations' in liste:
                categorie[int(m.group(1))] = 'realisation'
        # chaque carte <article> contient la photo (data-src) et le lien de l'article
        for bloc in page_liste.split('<article')[1:]:
            lien = re.search(r'/fr/news/(\d+)_', bloc)
            img = re.search(r'data-src="([^"]+\.(?:jpe?g|png|webp))"', bloc, re.I)
            if lien and img:
                u = img.group(1)
                images[int(lien.group(1))] = u if u.startswith('http') else SITE + u
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
    return nid, titre or 'Découvrez nos dernières actualités', date, categorie.get(nid, 'actualite'), images.get(nid)


IMAGE_ARTICLE = None   # photo de l'article, si on a pu la récupérer


def telecharger_image(url):
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        open('image-article.tmp', 'wb').write(r.content)
        im = Image.open('image-article.tmp'); im.load()
        if min(im.size) < 200:
            return None
        return 'image-article.tmp'
    except Exception as e:
        print('Image de l’article indisponible :', e)
        return None


def choisir_photo(nid, photos):
    if IMAGE_ARTICLE:
        return IMAGE_ARTICLE
    return photos[nid % len(photos)] if photos else None


def ecrire_lien(cat):
    cible = SITE + ('/fr/news/cat3_realisations' if cat == 'realisation' else '/fr/news/cat1_actualites')
    open('lien.html', 'w', encoding='utf-8').write(f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={cible}">
<link rel="canonical" href="{cible}">
<title>Mecalab</title>
<script>location.replace("{cible}");</script>
</head><body style="font-family:Arial,sans-serif">
<p>Redirection vers <a href="{cible}">{cible}</a>…</p>
</body></html>
''')


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
    src = choisir_photo(nid, photos)
    if src:  # photo de l'article, sinon une photo du dépôt
        ph = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
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
    for taille in (31, 28, 25, 22, 19):
        tf = font(TITRE, taille * S)
        lignes = couper(d, titre, tf, larg)
        haut = 176 * S - int(taille * 1.22) * S * (len(lignes) - 1) - taille * S
        if len(lignes) <= 3 and haut >= 98 * S:   # ne pas toucher le logo
            break
    lignes = lignes[:3]
    pas = int(taille * 1.22) * S
    y_bas = 176 * S
    y = y_bas - pas * (len(lignes) - 1)
    for l in lignes:
        d.text((tx, y), l, font=tf, fill='white', anchor='ls')
        y += pas
    d.line((tx, 188 * S, tx + 160 * S, 188 * S), fill=(200, 205, 215), width=S)
    sf = font(SS_SB, 12 * S)
    xx = tx
    for c in ('NOTRE DERNIÈRE RÉALISATION' if cat == 'realisation' else 'NOTRE DERNIÈRE ACTUALITÉ'):
        d.text((xx, 208 * S), c, font=sf, fill='white', anchor='ls')
        xx += d.textlength(c, font=sf) + 3.2 * S

    # bande bleue + icônes
    by = H - BAND
    d.rectangle((0, by, W, H), fill=BLUE)
    bf = font(SS_SB, 14 * S)
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


def generer_compact(nid, titre, date, cat='actualite', sortie='banniere-cote.jpg'):
    """Version compacte (380 x 210 px) à placer à droite des coordonnées."""
    CW, CH, CB = 380 * S, 210 * S, 36 * S
    photos = sorted(glob.glob('photo-*.jpg') + glob.glob('photo-*.jpeg') + glob.glob('photo-*.png'))
    ph_h = CH - CB
    img = Image.new('RGB', (CW, CH), NAVY)
    src = choisir_photo(nid, photos)
    if src:
        ph = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
        ratio = CW / ph_h
        if ph.width / ph.height > ratio:
            cw = int(ph.height * ratio); x0 = (ph.width - cw) // 2
            ph = ph.crop((x0, 0, x0 + cw, ph.height))
        else:
            ch = int(ph.width / ratio); y0 = int((ph.height - ch) * 0.45)
            ph = ph.crop((0, y0, ph.width, y0 + ch))
        img.paste(ph.resize((CW, ph_h), Image.LANCZOS), (0, 0))
    x = np.linspace(0, 1, CW)
    a = np.tile(0.93 - 0.62 * np.clip((x - 0.30) / 0.45, 0, 1), (ph_h, 1))[..., None]
    base = np.array(img.crop((0, 0, CW, ph_h))).astype(float)
    img.paste(Image.fromarray((base * (1 - a) + np.array(NAVY, float) * a).astype('uint8')), (0, 0))
    d = ImageDraw.Draw(img)

    D, cx, cy = 50 * S, 14 * S, 12 * S
    m = Image.new('L', (D * 4, D * 4), 0)
    ImageDraw.Draw(m).ellipse((0, 0, D * 4 - 1, D * 4 - 1), fill=255)
    img.paste(Image.new('RGB', (D, D), 'white'), (cx, cy), m.resize((D, D), Image.LANCZOS))
    logo = Image.open('logo-mecalab.png').convert('RGBA')
    lw = int(D * 0.82)
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    img.paste(logo, (cx + (D - lw) // 2, cy + (D - logo.height) // 2), logo)

    tx, larg = 16 * S, 250 * S
    for taille in (22, 20, 18, 16, 14):
        tf = font(TITRE, taille * S)
        lignes = couper(d, titre, tf, larg)
        haut = 122 * S - int(taille * 1.22 * S) * (len(lignes) - 1) - taille * S
        if len(lignes) <= 3 and haut >= 68 * S:   # ne pas toucher le logo
            break
    lignes = lignes[:3]
    pas = int(taille * 1.22 * S)
    y = 122 * S - pas * (len(lignes) - 1)
    for l in lignes:
        d.text((tx, y), l, font=tf, fill='white', anchor='ls')
        y += pas
    d.line((tx, 132 * S, tx + 110 * S, 132 * S), fill=(200, 205, 215), width=S)
    sf = font(SS_SB, 9 * S)
    xx = tx
    for c in ('NOTRE DERNIÈRE RÉALISATION' if cat == 'realisation' else 'NOTRE DERNIÈRE ACTUALITÉ'):
        d.text((xx, 151 * S), c, font=sf, fill='white', anchor='ls')
        xx += d.textlength(c, font=sf) + 2.2 * S

    by = CH - CB
    d.rectangle((0, by, CW, CH), fill=BLUE)
    bf = font(SS_SB, 12 * S)
    my = by + CB // 2
    w = int(1.6 * S)
    k = 0.75
    if date:
        x0, y0 = 16 * S, my - 8 * S
        q = lambda v: int(v * k * S)
        d.rounded_rectangle((x0, y0 + q(3), x0 + q(20), y0 + q(21)), radius=q(3), outline='white', width=w)
        d.line((x0, y0 + q(8), x0 + q(20), y0 + q(8)), fill='white', width=w)
        for kk in (5, 15):
            d.line((x0 + q(kk), y0, x0 + q(kk), y0 + q(5)), fill='white', width=w)
        for r in range(2):
            for c in range(3):
                px, py = x0 + q(4 + c * 5), y0 + q(11 + r * 5)
                d.rectangle((px, py, px + q(2), py + q(2)), fill='white')
        d.text((38 * S, my), date.capitalize(), font=bf, fill='white', anchor='lm')
    else:
        lib = 'Découvrir le projet' if cat == 'realisation' else 'Lire l’actualité'
        d.text((16 * S, my), lib, font=bf, fill='white', anchor='lm')
        ax = 16 * S + d.textlength(lib, font=bf) + 8 * S
        d.line((ax, my, ax + 12 * S, my), fill='white', width=w)
        d.polygon([(ax + 14 * S, my), (ax + 8 * S, my - 4 * S), (ax + 8 * S, my + 4 * S)], fill='white')
    loc = 'Villers-le-Bouillet'
    lx = CW - 16 * S - d.textlength(loc, font=bf)
    x0, y0 = lx - 20 * S, my - 8 * S
    q = lambda v: int(v * k * S)
    d.ellipse((x0 + q(2), y0, x0 + q(18), y0 + q(16)), outline='white', width=w)
    d.polygon([(x0 + q(4), y0 + q(12)), (x0 + q(16), y0 + q(12)), (x0 + q(10), y0 + q(22))], fill='white')
    d.ellipse((x0 + q(3) + 1, y0 + q(1) + 1, x0 + q(17) - 1, y0 + q(15) - 1), fill=BLUE)
    d.ellipse((x0 + q(7), y0 + q(5), x0 + q(13), y0 + q(11)), outline='white', width=w)
    d.text((lx, my), loc, font=bf, fill='white', anchor='lm')
    img.save(sortie, quality=88, optimize=True, progressive=True)


if __name__ == '__main__':
    if len(sys.argv) > 1:          # test manuel : python generer_banniere.py "Titre" "16 juillet 2026"
        generer(1, sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
        generer_compact(1, sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
        sys.exit(0)
    try:
        nid, titre, date, cat, url_img = derniere_news()
    except Exception as e:          # site injoignable : on garde l'ancienne bannière
        print('Pas de mise à jour :', e)
        sys.exit(0)
    print('Dernière news :', nid, cat, titre, date, url_img)
    if url_img:
        IMAGE_ARTICLE = telecharger_image(url_img)
    generer(nid, titre, date, cat)
    generer_compact(nid, titre, date, cat)
    ecrire_lien(cat)
