import io, json, os, random, subprocess, tempfile, wave, math
from pathlib import Path
import requests
from PIL import Image, ImageOps
import numpy as np

FEED = 'https://raw.githubusercontent.com/massagerai5-creator/moduscapsule-feed/refs/heads/main/moduscapsule_make_final_116.json'
W, H, FPS = 720, 1280, 24
SEG = 2.75
TRANSITION = 0.30
OUT = Path('output'); OUT.mkdir(exist_ok=True)


def run(cmd):
    print('Running:', ' '.join(str(x) for x in cmd)[:300], flush=True)
    subprocess.run(cmd, check=True)


def get_product():
    r = requests.get(FEED, timeout=40); r.raise_for_status()
    feed = r.json()
    items = [p for p in feed['products'] if p.get('active') and p.get('enabled_for_publish') and p.get('publish_ready')]
    if not items: raise RuntimeError('No ready products')
    # Index controlled externally to avoid repetitions. Start at first product for testing.
    idx = int(os.getenv('PRODUCT_INDEX', '0')) % len(items)
    return items[idx], len(items)


def download_photos(product, work):
    urls = [product.get('image_url')] + (product.get('additional_images') or [])
    photos = []
    for i, url in enumerate(dict.fromkeys(filter(None, urls))):
        try:
            resp = requests.get(url, timeout=35, headers={'User-Agent': 'Mozilla/5.0', 'Referer':'https://moduscapsule.ru/'})
            resp.raise_for_status()
            im = Image.open(io.BytesIO(resp.content)).convert('RGB')
            # blur-free center crop for 9:16; preserve original pixels, no fabricated features
            im = ImageOps.fit(im, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5,0.5))
            fp = work / f'photo_{i}.jpg'; im.save(fp, quality=91)
            photos.append(fp)
        except Exception as exc:
            print(f'Image {i} skipped: {exc}', flush=True)
        if len(photos) >= 6: break
    if len(photos) < 2: raise RuntimeError('Need at least 2 downloadable photos; check feed URLs')
    while len(photos) < 6: photos += photos[:min(len(photos), 6-len(photos))]
    return photos[:6]


def original_music(path):
    # Original instrumental electronic beat, not copyrighted music.
    rate = 32000; n = int(15*rate)
    audio = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(2026)
    bpm = 126
    for beat in np.arange(0, 15, 60/bpm):
        a=int(beat*rate); length=min(n-a, int(.28*rate)); t=np.arange(length)/rate
        kick=np.sin(2*np.pi*(65*t + (95-65)*(.035/(2*np.pi))* (1-np.exp(-t/.035))*2*np.pi)) * np.exp(-t*18)
        audio[a:a+length] += 0.58*kick.astype(np.float32)
    for h in np.arange(0, 15, 30/bpm):
        a=int(h*rate); length=min(n-a,int(.09*rate)); t=np.arange(length)/rate
        hiss=rng.standard_normal(length).astype(np.float32)*np.exp(-t*52)
        audio[a:a+length] += .085*hiss
    for b in np.arange(0, 15, 60/bpm*2):
        a=int(b*rate); length=min(n-a,int(.35*rate)); t=np.arange(length)/rate
        tone=np.sin(2*np.pi*110*t)*np.exp(-t*9)
        audio[a:a+length]+=.18*tone.astype(np.float32)
    # fade-in/out
    fade=int(.2*rate); audio[:fade]*=np.linspace(0,1,fade); audio[-fade:]*=np.linspace(1,0,fade)
    audio=np.clip(audio,-.96,.96)
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
        wav.writeframes((audio*32767).astype('<i2').tobytes())


def text_safe(s):
    return s.replace('\\','\\\\').replace(':','\\:').replace("'", "\\'").replace('%','\\%').replace(',','\\,')


def main():
    product, total=get_product()
    name=product.get('name','ModusCapsule')
    print('Generating:', name, 'of', total, flush=True)
    with tempfile.TemporaryDirectory() as td:
        work=Path(td); photos=download_photos(product,work)
        for i, fp in enumerate(photos):
            direction=1 if i%2==0 else -1
            # zoompan: noticeable zoom and motion, alternate direction, 66 frames each
            zoom = "min(zoom+0.0030,1.20)" if direction == 1 else "if(eq(on,1),1.20,max(zoom-0.0030,1.0))"
            x = "iw/2-(iw/zoom/2)+sin(on/13)*10" if i%2==0 else "iw/2-(iw/zoom/2)-sin(on/13)*10"
            y = "ih/2-(ih/zoom/2)"
            vf = f"zoompan=z='{zoom}':x='{x}':y='{y}':d={int(SEG*FPS)}:s={W}x{H}:fps={FPS},format=yuv420p"
            run(['ffmpeg','-y','-hide_banner','-loglevel','error','-loop','1','-i',str(fp),'-vf',vf,'-frames:v',str(int(SEG*FPS)),'-c:v','libx264','-preset','veryfast','-crf','24',str(work/f's{i}.mp4')])
        # Use whip pan on two changes and smooth diagonal wipe / dissolve for others.
        inputs=[]
        for i in range(6): inputs+=['-i',str(work/f's{i}.mp4')]
        filter_parts=[]
        types=['slideleft','fade','slideright','smoothleft','fade']
        for i, typ in enumerate(types):
            left='[0:v]' if i==0 else f'[x{i-1}]'
            right=f'[{i+1}:v]'
            out=f'[x{i}]'
            offset=(i+1)*(SEG-TRANSITION)
            filter_parts.append(f'{left}{right}xfade=transition={typ}:duration={TRANSITION}:offset={offset:.3f}{out}')
        font='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        if not Path(font).exists(): font='/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'
        # Feature captions only when backed by the selected product description.
        desc = str(product.get('description') or '').lower()
        rules = [
            ('панорамн', 'ПАНОРАМНОЕ ОСТЕКЛЕНИЕ'),
            ('климат-контрол', 'КЛИМАТ-КОНТРОЛЬ'),
            ('энергоэффектив', 'ЭНЕРГОЭФФЕКТИВНОСТЬ'),
            ('звукоизоляц', 'ЗВУКОИЗОЛЯЦИЯ'),
            ('умный дом', 'СИСТЕМА УМНЫЙ ДОМ'),
            ('освещени', 'СОВРЕМЕННОЕ ОСВЕЩЕНИЕ'),
            ('отделк', 'СОВРЕМЕННАЯ ОТДЕЛКА'),
            ('зонирован', 'УДОБНОЕ ЗОНИРОВАНИЕ'),
        ]
        features = []
        if 'террас' in desc and 'подогрев' in desc:
            features.append('ТЕРРАСА С ПОДОГРЕВОМ')
        for keyword, label in rules:
            if keyword in desc and label not in features:
                features.append(label)
        if 'готов' in desc and ('заселени' in desc or 'проживани' in desc):
            features.append('ГОТОВ К ЗАСЕЛЕНИЮ')

        draw = [
            f"[x4]drawtext=fontfile={font}:text='{text_safe(name)}':fontsize=54:fontcolor=white:"
            f"box=1:boxcolor=black@0.60:boxborderw=17:x=(w-text_w)/2:y=210:enable='between(t,0.2,2.5)'"
        ]
        for i, label in enumerate(features[:4]):
            start_t = 2.65 + i * 2.35
            end_t = min(start_t + 2.15, 12.0)
            draw.append(
                f"drawtext=fontfile={font}:text='{text_safe(label)}':fontsize=32:fontcolor=white:"
                f"box=1:boxcolor=black@0.72:boxborderw=15:"
                f"x=(w-text_w)/2:y=890:enable='between(t,{start_t:.2f},{end_t:.2f})'"
            )
        draw.extend([
            f"drawtext=fontfile={font}:text='MODUSCAPSULE':fontsize=45:fontcolor=white:"
            f"box=1:boxcolor=black@0.65:boxborderw=14:x=(w-text_w)/2:y=950:enable='between(t,12.1,15)'",
            f"drawtext=fontfile={font}:text='{text_safe('+7 (499) 653 65 88')}':fontsize=37:fontcolor=white:"
            f"box=1:boxcolor=black@0.70:boxborderw=15:x=(w-text_w)/2:y=1040:enable='between(t,12.1,15)'"
        ])
        filter_parts.append(','.join(draw) + '[v]')
        run(['ffmpeg','-y','-hide_banner','-loglevel','error',*inputs,'-filter_complex',';'.join(filter_parts),'-map','[v]','-an','-r',str(FPS),'-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p',str(work/'silent.mp4')])
        music=work/'music.wav'; original_music(music)
        output=OUT/'moduscapsule_reel.mp4'
        run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(work/'silent.mp4'),'-i',str(music),'-c:v','copy','-c:a','aac','-b:a','128k','-t','15','-movflags','+faststart',str(output)])
        (OUT/'reel_info.json').write_text(json.dumps({'id':product['id'],'name':name,'product_url':product.get('source_url'), 'filename':output.name},ensure_ascii=False,indent=2),encoding='utf-8')
        print('Ready:',output,flush=True)


if __name__=='__main__': main()
