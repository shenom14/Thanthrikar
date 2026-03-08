import pyaudio

def test_devices():
    p = pyaudio.PyAudio()
    count = p.get_device_count()
    print(f"Total audio devices found: {count}\n")
    
    for i in range(count):
        info = p.get_device_info_by_index(i)
        print(f"Device [{i}]: {info.get('name')}")
        print(f"  Max Input Channels: {info.get('maxInputChannels')}")
        print(f"  Max Output Channels: {info.get('maxOutputChannels')}")
        print(f"  Default Sample Rate: {info.get('defaultSampleRate')}\n")
        
    p.terminate()

if __name__ == "__main__":
    test_devices()
