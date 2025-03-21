import time
import torch
from ctc_forced_aligner import (
    load_audio,
    load_alignment_model,
    generate_emissions,
    get_alignments,
    get_spans,
    postprocess_results, 
    preprocess_text,
)



class Alignment:
    def __init__(self, device="cuda"):
        self.device = device
        self.alignment_model, self.alignment_tokenizer = load_alignment_model(
            self.device,
            dtype=torch.float16 if self.device == "cuda" else torch.float32,
        )
        #self.alignment_model = torch.compile(self.alignment_model,
        #    fullgraph=True,
        #    backend="inductor" if torch.cuda.is_available() else "aot_eager",
        #    mode="reduce-overhead" if torch.cuda.is_available() else None
        #)

    def fix_tokens(self, tokens_starred):
        tokens_starred = [' '.join([w for w in token.split(' ') if w != '-']) for token in tokens_starred]
        return tokens_starred

    def align(self, audio_path, text, language="iso", batch_size=16):
        audio_waveform = load_audio(audio_path, self.alignment_model.dtype, self.device)

        emissions, stride = generate_emissions(
            self.alignment_model, audio_waveform, batch_size=batch_size
        )
        for romanize in [False, True]:
            tokens_starred, text_starred = preprocess_text(
                text,
                romanize=romanize,
                language=language,
            )
            tokens_starred = self.fix_tokens(tokens_starred)
            try:
                segments, scores, blank_token = get_alignments(
                    emissions,
                    tokens_starred,
                    self.alignment_tokenizer,
                )
                spans = get_spans(tokens_starred, segments, blank_token)
                word_timestamps = postprocess_results(text_starred, spans, stride, scores)
                return word_timestamps
            except Exception:
                if romanize:
                    raise
                else:
                    import traceback
                    traceback.print_exc()
                    continue
            