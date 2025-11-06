# processar_video.py - Lógica de processamento
import os
import asyncio
import whisper
import yt_dlp
import json
import re
from groq import Groq
import moviepy.editor as mp
from moviepy.video.fx.all import crop, fadein, fadeout
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Configurações
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

async def processar_video_completo(youtube_url, user_id, status_callback):
    """Processa vídeo completo"""
    
    try:
        # Pasta temporária
        user_dir = f"/tmp/user_{user_id}"
        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(f"{user_dir}/output", exist_ok=True)
        
        logger.info(f"📁 Pasta criada: {user_dir}")
        
        # ===== DOWNLOAD =====
        await status_callback(
            "🔄 *Etapa 1/4: Download*\n\n"
            "⏬ Baixando vídeo..."
        )
        
        video_path = await download_youtube(youtube_url, user_dir)
        
        if not video_path:
            return {'sucesso': False, 'erro': 'Falha no download'}
        
        logger.info(f"✅ Vídeo: {video_path}")
        
        # ===== TRANSCRIÇÃO =====
        await status_callback(
            "🔄 *Etapa 2/4: Transcrição*\n\n"
            "🎤 Transcrevendo (5-10 min)..."
        )
        
        transcricao = await transcrever_video(video_path)
        
        if not transcricao:
            return {'sucesso': False, 'erro': 'Falha na transcrição'}
        
        logger.info(f"✅ {len(transcricao['segments'])} segmentos")
        
        # ===== MOMENTOS =====
        await status_callback(
            "🔄 *Etapa 3/4: Análise IA*\n\n"
            "🤖 Identificando momentos virais..."
        )
        
        momentos = await identificar_momentos(transcricao)
        
        if not momentos:
            return {'sucesso': False, 'erro': 'Nenhum momento identificado'}
        
        logger.info(f"✅ {len(momentos)} momentos")
        
        # ===== GERAR CLIPS =====
        await status_callback(
            f"🔄 *Etapa 4/4: Gerando Clips*\n\n"
            f"🎬 Criando {len(momentos)} clips..."
        )
        
        clips_paths = await gerar_clips(video_path, transcricao, momentos, user_dir, status_callback)
        
        if not clips_paths:
            return {'sucesso': False, 'erro': 'Falha ao gerar clips'}
        
        logger.info(f"✅ {len(clips_paths)} clips gerados")
        
        # Limpar
        try:
            os.remove(video_path)
        except:
            pass
        
        return {
            'sucesso': True,
            'clips': clips_paths,
            'titulos': [m['titulo'] for m in momentos]
        }
    
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        return {'sucesso': False, 'erro': str(e)}

async def download_youtube(url, output_dir):
    """Download do YouTube"""
    try:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': f'{output_dir}/video.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        video_path = f'{output_dir}/video.mp4'
        return video_path if os.path.exists(video_path) else None
    
    except Exception as e:
        logger.error(f"Erro download: {e}")
        return None

async def transcrever_video(video_path):
    """Transcrição com Whisper"""
    try:
        model = whisper.load_model("base")
        
        result = model.transcribe(
            video_path,
            language='pt',
            word_timestamps=True,
            fp16=False
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Erro transcrição: {e}")
        return None

async def identificar_momentos(transcricao):
    """Identificar momentos com Groq"""
    try:
        if not groq_client:
            return []
        
        texto = ""
        for seg in transcricao['segments']:
            texto += f"[{seg['start']:.1f}s] {seg['text']}\n"
        
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "system",
                "content": "Identifique momentos virais para TikTok. Retorne JSON."
            }, {
                "role": "user",
                "content": f"""Analise e retorne 7 momentos virais.

TRANSCRIÇÃO:
{texto[:15000]}

JSON:
[
  {{"titulo": "TÍTULO CLICKBAIT", "start": 10.0, "end": 50.0}},
  ... mais 6
]

Regras: 40-60s, português BR, REVELA/CONFESSA/CHOCANTE"""
            }],
            temperature=0.8,
            max_tokens=2000
        )
        
        resposta = response.choices[0].message.content
        resposta = resposta.replace('```json', '').replace('```', '').strip()
        json_match = re.search(r'\[\s*\{.*?\}\s*\]', resposta, re.DOTALL)
        
        if json_match:
            momentos = json.loads(json_match.group())
            return momentos[:7]
        
        return []
    
    except Exception as e:
        logger.error(f"Erro identificar: {e}")
        return []

async def gerar_clips(video_path, transcricao, momentos, user_dir, status_callback):
    """Gerar clips"""
    try:
        clips_gerados = []
        video = mp.VideoFileClip(video_path)
        
        # Crop 9:16
        original_w, original_h = video.w, video.h
        new_w = int(original_h * 9/16)
        new_h = original_h
        
        if new_w % 2 != 0:
            new_w -= 1
        if new_h % 2 != 0:
            new_h -= 1
        
        x1 = (original_w - new_w) // 2
        
        for i, momento in enumerate(momentos, 1):
            try:
                await status_callback(
                    f"🔄 *Etapa 4/4*\n\n"
                    f"🎬 Clip {i}/{len(momentos)}"
                )
                
                start = max(0, momento['start'] - 0.5)
                end = min(video.duration, momento['end'] + 0.5)
                
                clip = video.subclip(start, end)
                clip = crop(clip, x1=x1, width=new_w, height=new_h)
                
                try:
                    clip = fadein(clip, 0.3)
                    clip = fadeout(clip, 0.3)
                except:
                    pass
                
                safe_title = "".join(c for c in momento['titulo'] if c.isalnum() or c in (' ', '-'))[:30]
                output_path = f"{user_dir}/output/clip_{i:02d}_{safe_title}.mp4"
                
                clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    bitrate='4000k',
                    fps=30,
                    preset='ultrafast',
                    verbose=False,
                    logger=None
                )
                
                clip.close()
                
                if os.path.exists(output_path):
                    clips_gerados.append(output_path)
                    logger.info(f"✅ Clip {i}")
            
            except Exception as e:
                logger.error(f"❌ Clip {i}: {e}")
        
        video.close()
        return clips_gerados
    
    except Exception as e:
        logger.error(f"Erro gerar: {e}")
        return []
