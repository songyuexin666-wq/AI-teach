import os
import asyncio
from datetime import datetime
from typing import Optional
import tempfile
import shutil
import logging
import edge_tts
import pyttsx3

logger = logging.getLogger(__name__)

class TextToSpeechService:
    def __init__(self):
        self.supported_languages = {
            "zh": "Chinese",
            "en": "English", 
            "ja": "Japanese",
            "ko": "Korean",
            "fr": "French",
            "de": "German",
            "es": "Spanish"
        }
        
        # edge-tts语音映射
        self.voice_mapping = {
            "zh": "zh-CN-XiaoxiaoNeural",
            "en": "en-US-JennyNeural",
            "ja": "ja-JP-NanamiNeural",
            "ko": "ko-KR-SunHiNeural",
            "fr": "fr-FR-DeniseNeural",
            "de": "de-DE-KatjaNeural",
            "es": "es-ES-ElviraNeural"
        }

        # 离线 TTS（Windows SAPI / NSSpeechSynthesizer / espeak）
        # 注意：pyttsx3 输出一般是 wav，后续尽量保持格式一致
        self._offline_engine = None
        try:
            self._offline_engine = pyttsx3.init()
        except Exception as e:
            logger.warning(f"pyttsx3 初始化失败，将仅使用 edge-tts: {e}")
    
    async def generate_speech(
        self, 
        text: str, 
        language: str = "zh", 
        voice: Optional[str] = None,
        speed: float = 1.0
    ) -> str:
        """
        生成语音文件
        
        Args:
            text: 要转换的文本
            language: 语言代码
            voice: 声音类型（可选，edge-tts支持）
            speed: 语速（edge-tts支持）
            
        Returns:
            生成的音频文件名
        """
        try:
            if not text.strip():
                raise ValueError("文本内容不能为空")
            
            if language not in self.supported_languages:
                language = "zh"  # 默认使用中文
            
            # 选择语音
            selected_voice = voice or self.voice_mapping.get(language, "zh-CN-XiaoxiaoNeural")
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 优先尝试 mp3（edge-tts）；若失败则回退 wav（离线）
            audio_filename = f"speech_{timestamp}.mp3"
            output_path = os.path.join("outputs/audio", audio_filename)
            
            # 异步生成语音（优先 edge-tts）
            try:
                await self._generate_audio_file(text, selected_voice, output_path, speed)
            except Exception as e:
                # 403/网络问题：edge_tts 可能被限流或 token 失效，回退离线 TTS
                logger.warning(f"edge-tts 生成失败，尝试离线 TTS 回退: {e}")
                audio_filename = f"speech_{timestamp}.wav"
                output_path = os.path.join("outputs/audio", audio_filename)
                await asyncio.to_thread(self._generate_audio_file_offline, text, output_path, language, speed)
            
            return audio_filename
            
        except Exception as e:
            logger.error(f"语音生成失败: {str(e)}")
            raise
    
    async def _generate_audio_file(self, text: str, voice: str, output_path: str, speed: float = 1.0):
        """异步生成音频文件"""
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 修正语速计算：edge-tts 的 rate 是相对速度
            # 1.0 = 正常速度，2.0 = 2倍速，0.5 = 0.5倍速
            # 当 speed = 1.0 时，不设置 rate 参数，使用默认速度
            if speed == 1.0:
                communicate = edge_tts.Communicate(text, voice)
            else:
                rate_adjustment = f"{int((speed - 1) * 100)}%"
                communicate = edge_tts.Communicate(text, voice, rate=rate_adjustment)
            
            await communicate.save(output_path)
            
        except ValueError as e:
            logger.error(f"参数错误: {str(e)}")
            raise
        except RuntimeError as e:
            logger.error(f"运行时错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"音频文件生成失败: {str(e)}")
            raise

    def _generate_audio_file_offline(self, text: str, output_path: str, language: str = "zh", speed: float = 1.0):
        """离线生成音频文件（pyttsx3）。

        输出格式为 wav。用于 edge-tts 受限/403 时兜底，保证功能可用。
        """
        if not self._offline_engine:
            raise RuntimeError("离线 TTS 引擎不可用（pyttsx3 初始化失败）")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        engine = self._offline_engine
        try:
            # 语速：pyttsx3 默认 rate 大约 200；按 speed 做相对调整
            base_rate = engine.getProperty('rate') or 200
            engine.setProperty('rate', max(80, int(base_rate * float(speed))))

            # 语言/声音：不同系统 voice 列表不同，这里尽量挑中文/英文关键字匹配
            try:
                voices = engine.getProperty('voices') or []
                target = None
                if language == "zh":
                    for v in voices:
                        name = (getattr(v, "name", "") or "").lower()
                        vid = (getattr(v, "id", "") or "").lower()
                        if "chinese" in name or "zh" in name or "zh-cn" in name or "中文" in name or "chinese" in vid:
                            target = v.id
                            break
                elif language == "en":
                    for v in voices:
                        name = (getattr(v, "name", "") or "").lower()
                        if "english" in name or "en" in name:
                            target = v.id
                            break
                if target:
                    engine.setProperty('voice', target)
            except Exception:
                pass

            # 保存到文件
            engine.save_to_file(text, output_path)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"离线音频生成失败: {e}")
            raise
    
    async def generate_batch_speech(self, texts: list, language: str = "zh") -> list:
        """
        批量生成语音文件
        
        Args:
            texts: 文本列表
            language: 语言代码
            
        Returns:
            生成的音频文件名列表
        """
        tasks = []
        for text in texts:
            task = self.generate_speech(text, language)
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            audio_files = []
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"批量语音生成中的错误: {result}")
                    audio_files.append(None)
                else:
                    audio_files.append(result)
            
            return audio_files
            
        except Exception as e:
            logger.error(f"批量语音生成失败: {str(e)}")
            raise
    
    async def get_audio_info(self, audio_filename: str) -> dict:
        """获取音频文件信息"""
        audio_path = os.path.join("outputs/audio", audio_filename)
        
        if not os.path.exists(audio_path):
            raise Exception("音频文件不存在")
        
        stat = os.stat(audio_path)
        
        return {
            "filename": audio_filename,
            "size": stat.st_size,
            "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "path": audio_path,
            "format": "mp3"
        }
    
    def get_supported_languages(self) -> dict:
        """获取支持的语言列表"""
        return self.supported_languages
    
    async def text_to_speech_with_ssml(self, ssml_text: str, language: str = "zh") -> str:
        """
        使用SSML格式的文本生成语音
        edge-tts支持SSML
        """
        try:
            if not ssml_text.strip():
                raise ValueError("SSML文本内容不能为空")
            
            # 简单的SSML格式验证
            if not ssml_text.startswith("<speak") or not ssml_text.endswith("</speak>"):
                raise ValueError("SSML文本格式不正确，应该以<speak>开始，以</speak>结束")
            
            if language not in self.supported_languages:
                language = "zh"
            
            selected_voice = self.voice_mapping.get(language, "zh-CN-XiaoxiaoNeural")
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"speech_ssml_{timestamp}.mp3"
            output_path = os.path.join("outputs/audio", audio_filename)
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 使用edge-tts生成SSML语音
            communicate = edge_tts.Communicate(ssml_text, selected_voice)
            await communicate.save(output_path)
            
            return audio_filename
            
        except ValueError as e:
            logger.error(f"SSML格式错误: {str(e)}")
            raise
        except RuntimeError as e:
            logger.error(f"SSML语音生成运行时错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"SSML语音生成失败: {str(e)}")
            raise
