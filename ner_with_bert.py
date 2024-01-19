# -*- coding: utf-8 -*-
"""NER with BERT

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1pTCF2lKtmuvfVVeEzRBKQAT3svpV4weS
"""

pip install transformers

from google.colab import drive
drive.mount('/content/drive')

import pandas as pd
import torch
import numpy as np
from transformers import BertTokenizerFast, BertForTokenClassification
from torch.utils.data import DataLoader
from tqdm import tqdm
from torch.optim import SGD

path = '/content/drive/MyDrive/RA'

df = pd.read_csv(path+'/MiniProject/annotated_data_splitted_100ch_1.1.csv')
#df = pd.read_csv('annotated_data.csv')
df.drop(columns=['Unnamed: 0'], inplace=True)
df.head()

df.describe()

df = df[df['labels'].notna()]
df = df[df['text'].notna()]

tokenizer = BertTokenizerFast.from_pretrained('bert-base-cased')

label_all_tokens = False

def align_label(texts, labels):
    tokenized_inputs = tokenizer(texts, padding='max_length', max_length=512, truncation=True)

    word_ids = tokenized_inputs.word_ids()

    previous_word_idx = None
    label_ids = []

    for word_idx in word_ids:

        if word_idx is None:
            label_ids.append(-100)

        elif word_idx != previous_word_idx:
            try:
                label_ids.append(labels_to_ids[labels[word_idx]])
            except:
                label_ids.append(-100)
        else:
            try:
                label_ids.append(labels_to_ids[labels[word_idx]] if label_all_tokens else -100)
            except:
                label_ids.append(-100)
        previous_word_idx = word_idx

    return label_ids

class DataSequence(torch.utils.data.Dataset):

    def __init__(self, df):

        lb = [i.split() for i in df['labels'].values.tolist()]
        txt = df['text'].values.tolist()
        self.texts = [tokenizer(str(i),
                               padding='max_length', max_length = 512, truncation=True, return_tensors="pt") for i in txt]
        self.labels = [align_label(i,j) for i,j in zip(txt, lb)]

    def __len__(self):

        return len(self.labels)

    def get_batch_data(self, idx):

        return self.texts[idx]

    def get_batch_labels(self, idx):

        return torch.LongTensor(self.labels[idx])

    def __getitem__(self, idx):

        batch_data = self.get_batch_data(idx)
        batch_labels = self.get_batch_labels(idx)

        return batch_data, batch_labels

#df = df[0:1000]

labels = [i.split() for i in df['labels'].values.tolist()]
#print(labels)
unique_labels = set()

for lb in labels:
        [unique_labels.add(i) for i in lb if i not in unique_labels]
#print(unique_labels)
labels_to_ids = {k: v for v, k in enumerate(unique_labels)}
ids_to_labels = {v: k for v, k in enumerate(unique_labels)}
print(labels_to_ids)
print(ids_to_labels)

# df_train, df_val, df_test = np.split(df.sample(frac=1, random_state=42),
#                             [int(.3 * len(df)), int(.3 * len(df))])
# print(len(df))
# print(len(df_train))
# print(len(df_test))
# print(len(df_val))

df_train = df[:1000]
df_test = df[2000:52000]
df_val = df[1000:2000]

print(len(df_train))
print(len(df_test))
print(len(df_val))

df_train.reset_index(drop=True, inplace=True)
df_test.reset_index(drop=True, inplace=True)
df_val.reset_index(drop=True, inplace=True)

class BertModel(torch.nn.Module):

    def __init__(self):

        super(BertModel, self).__init__()

        self.bert = BertForTokenClassification.from_pretrained('bert-base-cased', num_labels=len(unique_labels))

    def forward(self, input_id, mask, label):

        output = self.bert(input_ids=input_id, attention_mask=mask, labels=label, return_dict=False)

        return output

def train_loop(model, df_train, df_val):

    train_dataset = DataSequence(df_train)
    val_dataset = DataSequence(df_val)

    train_dataloader = DataLoader(train_dataset, num_workers=4, batch_size=BATCH_SIZE, shuffle=True)
    val_dataloader = DataLoader(val_dataset, num_workers=4, batch_size=BATCH_SIZE)

    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")

    optimizer = SGD(model.parameters(), lr=LEARNING_RATE)

    if use_cuda:
        model = model.cuda()

    best_acc = 0
    best_loss = 1000

    for epoch_num in range(EPOCHS):

        total_acc_train = 0
        total_loss_train = 0

        model.train()

        for train_data, train_label in tqdm(train_dataloader):

            train_label = train_label.to(device)
            mask = train_data['attention_mask'].squeeze(1).to(device)
            input_id = train_data['input_ids'].squeeze(1).to(device)

            optimizer.zero_grad()
            loss, logits = model(input_id, mask, train_label)

            for i in range(logits.shape[0]):

              logits_clean = logits[i][train_label[i] != -100]
              label_clean = train_label[i][train_label[i] != -100]

              predictions = logits_clean.argmax(dim=1)
              acc = (predictions == label_clean).float().mean()
              total_acc_train += acc
              total_loss_train += loss.item()

            loss.backward()
            optimizer.step()

        model.eval()

        total_acc_val = 0
        total_loss_val = 0

        for val_data, val_label in val_dataloader:

            val_label = val_label.to(device)
            mask = val_data['attention_mask'].squeeze(1).to(device)
            input_id = val_data['input_ids'].squeeze(1).to(device)

            loss, logits = model(input_id, mask, val_label)

            for i in range(logits.shape[0]):

              logits_clean = logits[i][val_label[i] != -100]
              label_clean = val_label[i][val_label[i] != -100]

              predictions = logits_clean.argmax(dim=1)
              acc = (predictions == label_clean).float().mean()
              total_acc_val += acc
              total_loss_val += loss.item()

        val_accuracy = total_acc_val / len(df_val)
        val_loss = total_loss_val / len(df_val)

        print(
            f'Epochs: {epoch_num + 1} | Loss: {total_loss_train / len(df_train): .3f} | Accuracy: {total_acc_train / len(df_train): .3f} | Val_Loss: {total_loss_val / len(df_val): .3f} | Accuracy: {total_acc_val / len(df_val): .3f}')

LEARNING_RATE = 5e-3
EPOCHS = 1
BATCH_SIZE = 2

model = BertModel()
train_loop(model, df_train, df_val)

#torch.save(model, path+'/MiniProject/model_annotated_splitted_100ch_1.1_vaish')

# model = torch.load(path+'/MiniProject/model_annotated_stanford_100ch_1.1_vaish')
# model.eval()

def evaluate(model, df_test):

    test_dataset = DataSequence(df_test)

    test_dataloader = DataLoader(test_dataset, num_workers=4, batch_size=1)

    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")

    if use_cuda:
        model = model.cuda()

    total_acc_test = 0.0

    for test_data, test_label in test_dataloader:

            test_label = test_label.to(device)
            mask = test_data['attention_mask'].squeeze(1).to(device)

            input_id = test_data['input_ids'].squeeze(1).to(device)

            loss, logits = model(input_id, mask, test_label)

            for i in range(logits.shape[0]):

              logits_clean = logits[i][test_label[i] != -100]
              label_clean = test_label[i][test_label[i] != -100]

              predictions = logits_clean.argmax(dim=1)
              acc = (predictions == label_clean).float().mean()
              total_acc_test += acc

    val_accuracy = total_acc_test / len(df_test)
    print(f'Test Accuracy: {total_acc_test / len(df_test): .3f}')


evaluate(model, df_test)

"""Predicting a Sentence"""

def align_word_ids(texts):

    tokenized_inputs = tokenizer(texts, padding='max_length', max_length=512, truncation=True)

    word_ids = tokenized_inputs.word_ids()

    previous_word_idx = None
    label_ids = []

    for word_idx in word_ids:

        if word_idx is None:
            label_ids.append(-100)

        elif word_idx != previous_word_idx:
            try:
                label_ids.append(1)
            except:
                label_ids.append(-100)
        else:
            try:
                label_ids.append(1 if label_all_tokens else -100)
            except:
                label_ids.append(-100)
        previous_word_idx = word_idx

    return label_ids


def evaluate_one_text(model, sentence):


    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")

    if use_cuda:
        model = model.cuda()

    text = tokenizer(sentence, padding='max_length', max_length = 512, truncation=True, return_tensors="pt")

    mask = text['attention_mask'].to(device)
    input_id = text['input_ids'].to(device)
    label_ids = torch.Tensor(align_word_ids(sentence)).unsqueeze(0).to(device)

    logits = model(input_id, mask, None)
    logits_clean = logits[0][label_ids != -100]

    predictions = logits_clean.argmax(dim=1).tolist()
    prediction_label = [ids_to_labels[i] for i in predictions]
    #print('SENT: ', len(sentence.split()))
    #print(len(prediction_label))
    return prediction_label

evaluate_one_text(model, ' I LOVE  cannabis & lsd ')

len(df_test)

pred_arr = []
for j in range(len(df_test)):
  prediction = evaluate_one_text(model,df_test['text'][j])
  predicted = ''
  for i in prediction:
    predicted += i
    predicted += ' '
  pred_arr.append(predicted)

tn = 0
fn = 0
tp = 0
fp = 0
for i in range(len(pred_arr)):
  pred_sp = pred_arr[i].split()
  act_sp = df_test['labels'][i].split()
  if len(pred_sp) != len(act_sp):
    print('ERROR', i,len(pred_sp) ,len(act_sp))
    small_len = min(len(pred_sp),len(act_sp))
    print(small_len)
  else:
    small_len= len(pred_sp)
  for j in range(small_len):
    if pred_sp[j] == 'o' and act_sp[j] == 'o':
      tn += 1
    elif pred_sp[j] == 'o' and act_sp[j] != 'o':
      fn +=1
    elif pred_sp[j] != 'o' and act_sp[j] == 'o':
      fp += 1
    elif pred_sp[j] != 'o' and act_sp[j] != 'o':
      tp += 1
print('TN: ',tn)
print('FN: ',fn)
print('FP: ',fp)
print('TP: ',tp)
precision = (tp/(tp+fp))
recall = (tp/(tp+fn))
print('Precision: ', precision)
print('Recall: ', recall)
print('Accuracy: ', ((tp+tn)/(tn+fn+tp+fp)))
print('F1 Score: ', (2 * precision * recall)/(precision + recall))