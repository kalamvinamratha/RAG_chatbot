import React, { useEffect, useRef, useState } from 'react';
import { CircleNotch, Microphone } from '@phosphor-icons/react';

interface VoiceInputProps {
  onTranscribed: (text: string) => void;
  disabled?: boolean;
}

interface SpeechRecognitionInstance {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionInstance;
  webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
};

export const VoiceInput: React.FC<VoiceInputProps> = ({ onTranscribed, disabled }) => {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const transcriptionRef = useRef<AbortController | null>(null);
  const callbackRef = useRef(onTranscribed);
  const mountedRef = useRef(false);
  const [error, setError] = useState('');
  useEffect(() => {
    callbackRef.current = onTranscribed;
  }, [onTranscribed]);

  useEffect(() => {
    mountedRef.current = true;
    const SpeechRecognition =
      (window as SpeechWindow).SpeechRecognition ||
      (window as SpeechWindow).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          callbackRef.current(transcript);
        }
        setIsListening(false);
      };

      recognition.onerror = (event) => {
        console.warn('Speech recognition error:', event.error);
        setError('Dictation failed. Please retry or type your question.');
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
    return () => {
      mountedRef.current = false;
      const recognition = recognitionRef.current;
      if (recognition) {
        recognition.onend = null;
        recognition.onresult = null;
        recognition.onerror = null;
        recognition.abort();
      }
      transcriptionRef.current?.abort();
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.onstop = null;
        if (mediaRecorderRef.current.state === 'recording') mediaRecorderRef.current.stop();
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const toggleVoice = async () => {
    if (disabled || isProcessing) return;
    setError('');

    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    // Try SpeechRecognition first
    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
        setIsListening(true);
        return;
      } catch (e) {
        console.warn('SpeechRecognition failed to start, falling back to audio recording:', e);
      }
    }

    // Fallback: Audio recording & backend Whisper transcription
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        setIsProcessing(true);
        const audioBlob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType });
        const formData = new FormData();
        formData.append('file', audioBlob, 'clinical_dictation.webm');

        try {
          const controller = new AbortController();
          transcriptionRef.current = controller;
          const res = await fetch('/api/v1/voice/transcribe', {
            method: 'POST',
            body: formData,
            signal: controller.signal,
          });
          if (res.ok) {
            const data = await res.json();
            if (data.text) callbackRef.current(data.text);
          } else {
            throw new Error('Voice service unavailable');
          }
        } catch (err) {
          console.error('Transcription error:', err);
          if (!transcriptionRef.current?.signal.aborted)
            setError('Transcription failed. Please type your question.');
        } finally {
          if (!transcriptionRef.current?.signal.aborted) setIsProcessing(false);
          stream.getTracks().forEach((track) => track.stop());
        }
      };

      mediaRecorder.start();
      setIsListening(true);
    } catch (err) {
      console.warn('Microphone access denied:', err);
      setError('Microphone unavailable. Please type your question.');
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={toggleVoice}
        disabled={(disabled && !isListening) || isProcessing}
        aria-label={isListening ? 'Stop dictation' : 'Start voice dictation'}
        aria-pressed={isListening}
        className={`ui-button ui-icon-button relative ${
          isListening
            ? 'bg-destructive text-destructive-foreground ring-2 ring-ring/50'
            : 'bg-card  hover:bg-background  text-foreground  border border-border  shadow-xs'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        title={isListening ? 'Stop clinical dictation' : 'Clinical Voice Dictation (Add-on)'}
      >
        {isProcessing ? (
          <CircleNotch size={18} weight="bold" className="animate-spin text-primary " />
        ) : isListening ? (
          <>
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-destructive opacity-40" />
            <Microphone size={18} weight="fill" className="text-destructive-foreground" />
          </>
        ) : (
          <Microphone size={18} weight="duotone" className="text-muted-foreground " />
        )}
      </button>
      {error && (
        <span role="alert" className="text-xs text-destructive">
          {error}
        </span>
      )}
    </>
  );
};
