def get_audio_mime_type(audio_url):
    if audio_url.endswith('.wav'):
        return 'audio/wav'
    elif audio_url.endswith('.mp3'):
        return 'audio/mp3'
    elif audio_url.endswith('.aiff') or audio_url.endswith('.aif'):
        return 'audio/aiff'
    elif audio_url.endswith('.aac'):
        return 'audio/aac'
    elif audio_url.endswith('.ogg'):
        return 'audio/ogg'
    elif audio_url.endswith('.flac'):
        return 'audio/flac'
    else:
        return 'audio/mp3'