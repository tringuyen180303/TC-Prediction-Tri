# ---
# jupyter:
#   jupytext:
#     formats: py:light,ipynb
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.5
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %cd ../..

# +
#import sys  # noqa
#sys.path.append('../..')  # noqa

from tc_formation import plot
from tc_formation.data import data
import tc_formation.models.layers
import tc_formation.models.resnet as resnet
import tc_formation.tf_metrics as tfm
import tensorflow.keras as keras
import tensorflow as tf
from tensorflow.keras.layers.experimental import preprocessing
import tensorflow_addons as tfa
from datetime import datetime

# -

# Use ResNet

# The data that we're using will have the following shape.
# Should change it to whatever the shape of the data we're going to use down there.

# +
exp_name = 'baseline_resnet'
runtime = datetime.now().strftime('%Y_%b_%d_%H_%M')
# data_path = '/N/project/pfec_climo/qmnguyen/tc_prediction/extracted_test/6h_700mb'
#data_path = '/N/project/pfec_climo/qmnguyen/tc_prediction/extracted_features/alllevels_ABSV_CAPE_RH_TMP_HGT_VVEL_UGRD_VGRD/6h_700mb'
# data_path = '/N/project/pfec_climo/qmnguyen/tc_prediction/extracted_features/wp_ep_alllevels_ABSV_CAPE_RH_TMP_HGT_VVEL_UGRD_VGRD_100_260/12h_700mb'
# data_path = '/N/project/pfec_climo/qmnguyen/tc_prediction/extracted_features/multilevels_ABSV_CAPE_RH_TMP_HGT_VVEL_UGRD_VGRD/6h_700mb'
#data_path = '/N/project/pfec_climo/qmnguyen/tc_prediction/extracted_features/nolabels_wp_ep_alllevels_ABSV_CAPE_RH_TMP_HGT_VVEL_UGRD_VGRD_100_260/12h/tc_ibtracs_12h.csv'
#data_path = "/N/slate/trihnguy/ncep_netcdf3/tc_12h.csv"
#data_path = "/N/project/pfec_climo/qmnguyen/tc_prediction/extracted_features/ncep_netcdf3/tc_12h.csv"
#data_path = "/N/slate/trihnguy/east_sea_fnl_extracted/tc_18h.csv"
data_path = "/N/slate/trihnguy/fnl_14var_extracted_small/tc_72h.csv"
train_path = data_path.replace('.csv', '_train.csv')
val_path = data_path.replace('.csv', '_val.csv')
test_path = data_path.replace('.csv', '_test.csv')
subset = dict(
    absvprs=[900, 750],
    rhprs=[750],
    tmpprs=[900, 500],
    hgtprs=[500],
    vvelprs=[500],
    ugrdprs=[800, 200],
    vgrdprs=[800, 200],
    tmptrp=True,
    hgttrp=True
)
'''
subset = dict(
    ugrdprs=[800, 200],
    vgrdprs=[800, 200],
    rhprs= [750])
'''

# Data variables # 1
"""
subset = dict(
ugrdprs = [ 800, 200],
vgrdprs= [ 800, 200],
rhprs= [750],
capesfc=True,
tmpsfc=True)
"""



# Data with 7 variables #2

# subset = dict(
#     ugrdprs=[800, 200],
#     vgrdprs=[800, 200],
#     rhprs= [750],
#     vvelprs=[500],
#     tmpprs = [500])
# data_shape = (41, 161, 7)

# Data 9 variables 
# subset = dict(
#     ugrdprs=[800, 200],
#     vgrdprs=[800, 200],
#     rhprs= [750],
#     vvelprs=[500],
#     tmpprs = [500],
#     capesfc = True,
#     tmpsfc=True
#     )
# data_shape = (41, 161, 9)
"""
subset = dict(
    absvprs=[900, 750],
    capesfc=True,
    hgtprs=[500],
    rhprs=[750],
    tmpprs=[900, 500],
    tmpsfc=True,
    ugrdprs=[800, 200],
    vgrdprs=[800, 200],
    vvelprs=[500],
    tmptrp=True,
    hgttrp=True
)

data_shape = (21, 56, 15)"""

data_shape = (21, 56, 13)
# -

model = resnet.ResNet18(
    input_shape=data_shape,
    include_top=True,
    classes=1,
    classifier_activation=None,)
model.summary()

# Build the model using BinaryCrossentropy loss

model.compile(
    optimizer='adam',
    # loss=tf.keras.losses.BinaryCrossentropy(from_logits=True),
    loss=tfa.losses.SigmoidFocalCrossEntropy(from_logits=True),
    metrics=[
        'binary_accuracy',
        tfm.RecallScore(from_logits=True),
        tfm.PrecisionScore(from_logits=True),
        tfm.CustomF1Score(from_logits=True),
    ]
)

# Load our training and validation data.

# +
full_training = data.load_data_v1(
    train_path,
    data_shape=data_shape,
    batch_size=64,
    shuffle=True,
    subset=subset,
    group_same_observations=False,
)
# downsampled_training = data.load_data(
#     train_path,
#     data_shape=data_shape,
#     batch_size=64,
#     shuffle=True,
#     subset=subset,
#     negative_samples_ratio=1)
validation = data.load_data_v1(
    val_path,
    data_shape=data_shape,
    subset=subset,
    group_same_observations=True,
)

for _ in iter(full_training):
    print('Preload training')
print('Training data preloaded')

for _ in iter(validation):
    print('Preload validation')
print('Validation preloaded')
# -

features = full_training.map(lambda X, _: X)

normalizer = preprocessing.Normalization()

normalizer.adapt(features)


# +
def normalize_data(x, y):
    return normalizer(x), y


full_training = full_training.map(normalize_data)
# downsampled_training = downsampled_training.map(normalize_data)
validation = validation.map(normalize_data)
# -

# # First stage
#
# train the model on the down-sampled data.

# +
epochs = 150
first_stage_history = model.fit(
    # downsampled_training,
    full_training,
    epochs=epochs,
    validation_data=validation,
    class_weight={1: 10., 0: 1.},
    shuffle=False,
    callbacks=[
        keras.callbacks.EarlyStopping(
            monitor='val_f1_score',
            mode='max',
            verbose=1,
            patience=20,
            restore_best_weights=True),
        keras.callbacks.ModelCheckpoint(
            filepath=f"outputs/{exp_name}_{runtime}_1st_ckp",
            monitor='val_f1_score',
            mode='max',
            save_best_only=True,
        ),
        keras.callbacks.TensorBoard(
            log_dir=f'outputs/{exp_name}_{runtime}_1st_board',
        ),
    ]
)

plot.plot_training_history(first_stage_history, "First stage training")

# +

testing = data.load_data_v1(
    test_path,
    data_shape=data_shape,
    subset=subset,
    group_same_observations=True,
)

# Evaluate for 15 vars
print(data_path)
subset_dataset = testing.skip(9)
subset_dataset = subset_dataset.skip(2)
subset = subset_dataset.map(normalize_data)
model.evaluate(
    subset,
    callbacks=[
        keras.callbacks.TensorBoard(
            log_dir=f'outputs/{exp_name}_{runtime}_1st_board',
        ),
    ])

# Evaluate for others


testing = testing.map(normalize_data)
model.evaluate(
    testing,
    callbacks=[
        keras.callbacks.TensorBoard(
            log_dir=f'outputs/{exp_name}_{runtime}_1st_board',
        ),
    ])


"""
# Obtain performance value at different thresholds."""
# -

import numpy as np
#print(predicted.type())
print(np.where(np.isnan(predicted) == True))

print(predicted[321])

print(len(predicted))

# +

testing = data.load_data_v1(
    test_path,
    data_shape=data_shape,
    subset=subset,
    group_same_observations=True,
)


# -

train_data = [(example.numpy(), label.numpy()) for example, label in testing]
print(len(train_data))


# +
first_element = testing.take(321)
image, label = list(first_element)[9]





# -

new = np.array(testing)
new.size

new

np.drop(new, [0], axis=0)

first_element = testing.take(321)
image, label = list(first_element)[9]
print(len(label))
print(image[0], label)

thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
for t in thresholds:
    model.compile(
        optimizer='adam',
        # loss=tf.keras.losses.BinaryCrossentropy(from_logits=True),
        loss=tfa.losses.SigmoidFocalCrossEntropy(from_logits=True),
        metrics=[
            'binary_accuracy',
            tfm.RecallScore(thresholds=t, from_logits=True),
            tfm.PrecisionScore(thresholds=t, from_logits=True),
            tfm.CustomF1Score(thresholds=t, from_logits=True),
        ]
    )
    print(f'=== Threshold {t} ===')
    model.evaluate(testing)

model.predict(testing)

print(testing)

# # Second stage
#
# train the model on full dataset.

# + active=""
# print(testing)

# +
# second_stage_history = model.fit(
#     full_training,
#     epochs=epochs,
#     validation_data=validation,
#     class_weight={1: 10., 0: 1.},
#     shuffle=True,
#     callbacks=[
#         keras.callbacks.EarlyStopping(
#             monitor='val_f1_score',
#             mode='max',
#             verbose=1,
#             patience=20,
#             restore_best_weights=True),
#         keras.callbacks.ModelCheckpoint(
#             filepath=f"outputs/{exp_name}_{runtime}_2nd_ckp",
#             monitor='val_f1_score',
#             mode='max',
#             save_best_only=True,
#         ),
#     ])


# plot.plot_training_history(second_stage_history, "Second stage training")
# -

# After the model is trained, we will test it on test data.

# model.evaluate(testing)

len(testing)

import numpy as np
array = []
for i in range(len(testing)):
    if i != 9:
        array.append([array, label])
    print(i)
print(len(array))

print(model.predict(testing))

array[0][0][0][0][0][0][0]

testing[:8]

# +
num_elements_to_view = 8

# Use the take() method to create a new dataset with the first few elements


# Iterate through the subset dataset to view its elements
for image_batch, label_batch in subset_dataset:
    # Process your data here
    print("Image batch shape:", image_batch.shape)
    print("Label batch shape:", label_batch.shape)
    print("First image in batch:", image_batch[0])
    print("First label in batch:", label_batch[0])
    print("\n")
# -

np.where(np.isnan(model.predict(subset_dataset)))

# +

np.where(np.isnan(model.predict(subset_dataset)))
# -





