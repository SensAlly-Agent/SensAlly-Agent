"""
Audio playback module for English learning
Uses OpenAI TTS only
"""

import json
from typing import Optional, Set
from pathlib import Path
import requests


class AudioDownloader:
    """Download and cache audio files using OpenAI TTS"""

    @staticmethod
    def get_openai_audio(
        word: str, 
        pronunciation: str, 
        audio_dir: Path,
        jwt_token: str = None,
        fastapi_url: str = None
    ) -> Optional[str]:
        """
        Generate audio using OpenAI TTS via /api/tts endpoint (with proper billing)
        pronunciation: "uk" or "us"
        jwt_token: JWT token for authentication
        fastapi_url: FastAPI server URL (e.g., "http://localhost:8000")
        """
        # 如果没有提供 token 或 url，跳过 OpenAI TTS
        if not jwt_token or not fastapi_url:
            print(f"跳过 OpenAI TTS for '{word}': 未提供 jwt_token 或 fastapi_url")
            return None
        
        # Voice selection based on accent
        voice_map = {
            "uk": "fable",  # British accent voice (expressive and dynamic)
            "us": "alloy"   # American-like voice (neutral)
        }

        voice = voice_map.get(pronunciation, "alloy")

        # File path for caching (清理特殊字符)
        safe_word = word.lower().replace("/", "_")
        filename = f"{safe_word}_{pronunciation}_openai.mp3"
        file_path = audio_dir / filename

        # Return cached file if exists
        if file_path.exists():
            return str(file_path)

        # Try to generate audio via /api/tts endpoint (with billing)
        try:
            response = requests.post(
                f"{fastapi_url}/api/tts",
                json={
                    "text": word,
                    "model": "gpt-4o-mini-tts",
                    "voice": voice
                },
                headers={"Authorization": f"Bearer {jwt_token}"},
                timeout=30
            )

            if response.status_code == 200:
                file_path.write_bytes(response.content)
                print(f"✅ OpenAI TTS 成功: {word} (via /api/tts)")
                return str(file_path)
            elif response.status_code == 402:
                print(f"⚠️ OpenAI TTS 跳过 '{word}': 额度不足")
            elif response.status_code == 401:
                print(f"⚠️ OpenAI TTS 跳过 '{word}': JWT token 无效或过期")
            else:
                print(f"❌ OpenAI TTS 失败 '{word}': HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            print(f"❌ OpenAI TTS 超时 '{word}'")
        except Exception as e:
            print(f"❌ OpenAI TTS 失败 '{word}': {e}")

        return None


class AudioPlayer:
    """Main audio player class - OpenAI TTS only"""

    def __init__(self, audio_dir: str = None):
        """Initialize audio player with audio directory"""
        if audio_dir:
            self.audio_dir = Path(audio_dir)
        else:
            # Default to script directory/audio
            script_dir = Path(__file__).parent
            self.audio_dir = script_dir / "audio"

        # Create directory if it doesn't exist
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        # Load cached audio file list
        self.audio_cache = self._load_audio_cache()

    def _load_audio_cache(self) -> Set[str]:
        """Load list of cached audio files"""
        cache_file = self.audio_dir / "cache.json"
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        return set()

    def _save_audio_cache(self):
        """Save audio cache list"""
        cache_file = self.audio_dir / "cache.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.audio_cache), f)

    def _add_to_cache(self, filename: str):
        """Add filename to cache"""
        self.audio_cache.add(filename)
        self._save_audio_cache()

    def get_audio_path(
        self, 
        word: str, 
        pronunciation: str, 
        jwt_token: str = None,
        fastapi_url: str = None
    ) -> Optional[str]:
        """
        Get audio file path for a word using OpenAI TTS
        Args:
            word: The word to get audio for
            pronunciation: "uk" or "us"
            jwt_token: JWT token for OpenAI TTS billing
            fastapi_url: FastAPI server URL for OpenAI TTS billing
        Returns:
            Path to audio file or None
        """
        audio_path = AudioDownloader.get_openai_audio(
            word, pronunciation, self.audio_dir,
            jwt_token=jwt_token, fastapi_url=fastapi_url
        )

        # Add to cache if successful
        if audio_path:
            self._add_to_cache(Path(audio_path).name)

        return audio_path



# Helper function
def load_toefl_vocabulary(file_path: str) -> dict:
    """Load TOEFL vocabulary from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    """Example usage"""
    # Initialize audio player
    player = AudioPlayer()


if __name__ == "__main__":
    main()