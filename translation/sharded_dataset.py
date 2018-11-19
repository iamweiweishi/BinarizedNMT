import os
import csv
import torch
import torchtext
import torchvision.transforms as transforms
import torch.utils.data as data
import random
from typing import Tuple

from vocab import Vocabulary, save_vocab, build_vocab, load_vocab
from utils import get_num_lines
from constants import WMT14_EN_FR_TRAIN_SHARD, TRAIN_EN_VOCAB_FILE, TRAIN_FR_VOCAB_FILE

# stores the entry src, trg for
# translation
Entry_Type = Tuple[str, str]

class ShardedDataset(object):
    def __init__(self):
        raise NotImplementedError()
    
    def __len__(self) -> int:
        raise NotImplementedError()
    
    def __iter__(self):
        return self
    
    def __next__(self) -> Entry_Type:
        raise NotImplementedError()

class ShardedCSVDataset(ShardedDataset):
    '''
    This dataset assumes that a larger dataset has been broken apart into
    a series of shards. All of which are defined as csv files, in the format
    src_line, translated_line.

    This dataset will retrieve each of the lines

    Arguments:
        sharded_dir: the directory with all the shards
    '''
    def __init__(self, sharded_dir: str, shuffle: bool = False):
        self.sharded_dir = sharded_dir
        self.shuffle = shuffle
        self.sharded_files = os.listdir(self.sharded_dir)

        self.sharded_files = [
            os.path.join(self.sharded_dir, file_name) for file_name in self.sharded_files
        ]

        if shuffle:
            random.shuffle(self.sharded_files)

        self.file_counts = {
            file_name : get_num_lines(file_name)
            for file_name in self.sharded_files
        }

        self.curr_file = None
        self.curr_file_name = None
        self.curr_idx = 0
        self.curr_data = []

        self.shard_idx = -1
    
    def __len__(self):
        return sum(self.file_counts.values())
    
    def reset(self):
        self.curr_file = None
        self.curr_file_name = None
        self.curr_idx = 0
        self.curr_data = []
        self.shard_idx = -1
    
    def __next__(self) -> Entry_Type:
        if self.curr_file is None or self.curr_idx >= self.file_counts[self.curr_file_name]:
            # read the new file into memory
            self.curr_file.close() if self.curr_file is not None else None

            self.shard_idx += 1

            if (self.shard_idx >= len(self.sharded_files)):
                # reached the end of the dataset
                raise StopIteration

            file_name = self.sharded_files[self.shard_idx]
            self.curr_file = open(file_name)
            self.curr_file_name = file_name
            self.curr_idx = 0
            
            # read the file into the dataset
            reader = csv.reader(self.curr_file, delimiter=',')
            self.curr_data = [(row[0], row[1]) for row in reader]

            if self.shuffle:
                random.shuffle(self.curr_data)
        
        # return the current line (src,  trg)
        val = self.curr_data[self.curr_idx]
        self.curr_idx += 1
        return val

class ShardedBatchedIterator(object):
    def __init__(
        self, 
        batch_size: int,
        data: ShardedDataset,
        en_vocab: Vocabulary,
        fr_vocab: Vocabulary,
        max_sequence_length: int,
    ):
        self.batch_size = batch_size
        self.data = data
        self.en_vocab = en_vocab
        self.fr_vocab = fr_vocab
        self.max_sequence_length = max_sequence_length
    
    def __next__(self) -> torch.Tensor:
        count = 0
        curr = next(self.data, None)

        if curr is None:
            raise StopIteration

        src = []
        trg = []
        while curr is not None and count < batch_size:
            src.append(curr[0])
            trg.append(curr[1])
            curr = next(self.data)
            count += 1

        # res has a series of tuples that are the src and the output
        src_tensor = torch.Tensor((count, self.max_sequence_length)).long()
        trg_tensor = torch.Tensor((count, self.max_sequence_length)).long()

        for i in range(count):
            src_tensor[i][:len(src[i])] = [self.en_vocab.word2idx(word) for word in src[i]]
            trg_tensor[i][:len(trg[i])] = [self.fr_vocab.word2idx(word) for word in trg[i]]
        
        return src_tensor, trg_tensor

def save_shard_vocab() -> None:
    '''
    Reads the shard dataset and creates vocabulary objects
    '''
    d = ShardedCSVDataset(WMT14_EN_FR_TRAIN_SHARD)

    def en_fn(item):
        return item[0]

    def fr_fn(item):
        return item[1]
    

    en_vocab = build_vocab(
        d,
        en_fn,
        unk_cutoff=2
    )

    d.reset()

    fr_vocab = build_vocab(
        d,
        fr_fn,
        unk_cutoff=2
    )

    save_vocab(en_vocab, TRAIN_EN_VOCAB_FILE)
    save_vocab(fr_vocab, TRAIN_FR_VOCAB_FILE)

def test() -> None:
    en_vocab = load_vocab(TRAIN_EN_VOCAB_FILE)
    fr_vocab = load_vocab(TRAIN_FR_VOCAB_FILE)

    print(
        "English Vocab Size: {} French Vocab Size: {}".format(len(en_vocab), len(fr_vocab))
    )

if __name__ == "__main__":
    save_shard_vocab()
    test()