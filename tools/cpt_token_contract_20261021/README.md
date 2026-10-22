# Public Base token/mask prerequisite

This is an offline reference and failure-reproduction tool, not a training
recipe, tokenizer rollout, MaxText patch, or claim of model improvement. It
does not load weights, download data, execute dataset programs, or access Kaggle.

The pinned Qwen Base has PAD = EOS = 248044 and no BOS. A real terminal EOS
must receive next-token loss, while identical token IDs used for padding must
not. The contract shifts original role masks with the labels, derives attention
from sequence length, uses zero padding for segmentation/positions, and refuses
truncation or multi-document packing. SFT preserves prompt attention while
masking its target loss. It requires a genuine nonempty answer before EOS.

Run mechanical tests:

    python -m unittest tests.test_cpt_token_contract_20261021

Run the real, hash-pinned public tokenizer check using the existing offline
tokenizers dependency. This consumes no downloaded dataset, only six manufactured
grid/code/Unicode strings. Choose a new report path; existing reports are never
overwritten:

    python -m tools.cpt_token_contract_20261021.probe \
      --tokenizer-root /path/to/verified/public/tokenizer \
      --output /path/to/new-report.json

The probe records exact generated IDs and reproduces how an ID-based PAD mask
loses one valid EOS target per document. Roundtrip preserves the tested whitespace,
NFC Unicode and code indentation. The actual Base tokenizer has an NFC normalizer:
it changes decomposed Unicode. The probe reproduces this change and the input
helper defaults to rejecting non-NFC source until an explicit transformation
policy is chosen. Ordinary text can use `native_nfc_with_receipt`, retaining the
original and normalized UTF-8 hashes and a changed flag. Code and exact targets
remain conditional on a separate semantic policy. This is not a blanket ban on
NFC or non-NFC data, a tokenizer modification, or a claim of byte-preserving
encoding. The probe verifies this explicit ordinary-text route too.
A literal internal EOS is rejected, not silently
treated as a document boundary. This is a deployment/input-contract defect to
prevent, not evidence that it caused historical IRIS scores.

Remaining integration gate: an actual chosen input pipeline must consume and
preserve these fields, and its loss must match the reference. No unmodified
MaxText compatibility is claimed. SFT callers must establish their boundary on
the tokenization of the joined prompt and answer; separately tokenizing and
concatenating is not asserted equivalent. Packed GDN sequences require their own
state-reset/isolation evidence and are deliberately not supported here.
