# bot.py - Bot do Telegram para Clips Virais
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from processar_video import processar_video_completo

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variáveis de ambiente
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_USER_ID', '0'))

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN não configurado!")

# ===== COMANDOS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "🎬 *Gerador de Clips Virais*\n\n"
        "Envie um link do YouTube e eu vou:\n\n"
        "✅ Transcrever automaticamente\n"
        "✅ Identificar 7 momentos virais\n"
        "✅ Gerar clips 9:16 com legendas\n"
        "✅ Enviar de volta para você\n\n"
        "⏱️ Tempo: 10-15 minutos\n\n"
        "💡 *Envie o link agora!*",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    await update.message.reply_text(
        "📖 *Como usar:*\n\n"
        "1️⃣ Envie um link do YouTube\n"
        "2️⃣ Aguarde o processamento\n"
        "3️⃣ Receba 7 clips prontos!\n\n"
        "🔗 Formatos aceitos:\n"
        "• youtube.com/watch?v=...\n"
        "• youtu.be/...\n\n"
        "❓ Dúvidas? Fale com @gxbriex",
        parse_mode='Markdown'
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Estatísticas (apenas admin)"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Comando apenas para admin")
        return
    
    await update.message.reply_text(
        "📊 *Estatísticas:*\n\n"
        "Status: Online ✅\n"
        "Servidor: Render\n"
        f"Admin: {ADMIN_ID}",
        parse_mode='Markdown'
    )

# ===== PROCESSAR LINK =====

async def processar_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa link do YouTube"""
    
    user = update.effective_user
    message_text = update.message.text
    
    logger.info(f"📨 Usuário @{user.username} ({user.id}) enviou: {message_text}")
    
    # Validar link
    if not ('youtube.com' in message_text or 'youtu.be' in message_text):
        await update.message.reply_text(
            "❌ *Link inválido!*\n\n"
            "Envie um link do YouTube:\n"
            "• youtube.com/watch?v=...\n"
            "• youtu.be/...",
            parse_mode='Markdown'
        )
        return
    
    # Mensagem de status
    status_msg = await update.message.reply_text(
        "✅ *Link recebido!*\n\n"
        "🔄 Iniciando processamento...\n"
        "⏱️ Tempo estimado: 10-15 min\n\n"
        "Você será notificado! ⏰",
        parse_mode='Markdown'
    )
    
    try:
        # Callback para atualizar status
        async def atualizar(texto):
            try:
                await status_msg.edit_text(texto, parse_mode='Markdown')
            except:
                pass
        
        # Processar vídeo
        resultado = await processar_video_completo(
            youtube_url=message_text,
            user_id=user.id,
            status_callback=atualizar
        )
        
        if resultado['sucesso']:
            # Atualizar status
            await status_msg.edit_text(
                f"✅ *Processamento concluído!*\n\n"
                f"📊 {len(resultado['clips'])} clips gerados\n"
                f"📤 Enviando arquivos...",
                parse_mode='Markdown'
            )
            
            # Enviar clips
            for i, clip_path in enumerate(resultado['clips'], 1):
                try:
                    with open(clip_path, 'rb') as video:
                        await update.message.reply_video(
                            video=video,
                            caption=f"🎬 *Clip {i}/{len(resultado['clips'])}*\n\n{resultado['titulos'][i-1]}",
                            parse_mode='Markdown',
                            supports_streaming=True,
                            width=1080,
                            height=1920
                        )
                    
                    logger.info(f"✅ Clip {i} enviado")
                    await asyncio.sleep(2)
                
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar clip {i}: {e}")
            
            # Mensagem final
            await update.message.reply_text(
                "🎉 *Pronto!*\n\n"
                "Todos os clips foram enviados.\n\n"
                "💡 Quer processar outro? Envie o link!",
                parse_mode='Markdown'
            )
        
        else:
            # Erro
            await status_msg.edit_text(
                f"❌ *Erro:*\n\n{resultado['erro']}\n\n"
                "Tente novamente ou fale com @gxbriex",
                parse_mode='Markdown'
            )
    
    except Exception as e:
        logger.error(f"❌ Erro geral: {e}")
        
        await status_msg.edit_text(
            "❌ *Erro inesperado!*\n\n"
            "Tente novamente em alguns minutos.",
            parse_mode='Markdown'
        )

# ===== MAIN =====

def main():
    """Iniciar bot"""
    
    logger.info("🚀 Iniciando Clips Virais Bot...")
    logger.info(f"📱 Telegram Token: {TELEGRAM_TOKEN[:10]}...")
    logger.info(f"👤 Admin ID: {ADMIN_ID}")
    
    # Criar aplicação
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_link))
    
    # Iniciar polling
    logger.info("✅ Bot online e aguardando mensagens!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
