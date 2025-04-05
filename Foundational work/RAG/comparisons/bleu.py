from sacrebleu.metrics import BLEU, CHRF, TER

# Example: Reference and candidate sentences
references = [['The dog bit the man.', 'It was not unexpected.']]  # List of lists
candidates = ['The dog bit the man.', "It wasn't surprising."]  # List of strings

bleu = BLEU()

score = bleu.corpus_score(candidates, references)
print(score)

sig = bleu.get_signature()
print(sig)

chrf = CHRF()
chrfScore = chrf.corpus_score(candidates, references)
print(chrfScore)