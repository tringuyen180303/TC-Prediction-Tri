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

# %load_ext autoreload
# %autoreload 2

# +
# #!conda install -c conda-forge opencv
# -

from tc_formation.data import data
from collections import OrderedDict
from datetime import datetime
from tc_formation.models import unet
from tc_formation import tf_metrics as tfm
import tc_formation.metrics.bb as bb
import tc_formation.data.time_series as ts_data
from tc_formation.losses.hard_negative_mining import hard_negative_mining
import tensorflow as tf
import tensorflow.keras as keras
from tensorflow.keras.layers.experimental import preprocessing
import tensorflow_addons as tfa
import xarray as xr
from tc_formation import plot

# # Predict TC Formation using Grid Probability

# Configurations to run for this experiment.

# +
exp_name = 'tc_grid_prob_unet'
runtime = datetime.now().strftime('%Y_%b_%d_%H_%M')
LEADTIME = 60
#data_path = 'data/nolabels_wp_ep_alllevels_ABSV_CAPE_RH_TMP_HGT_VVEL_UGRD_VGRD_100_260/12h/tc_ibtracs_6h_12h_18h_24h_30h_36h_42h_48h.csv'
#data_path = "/N/slate/trihnguy/east_sea_fnl_extracted/tc_12h.csv"
#data_path = "/N/slate/trihnguy/ncep_netcdf3/tc_12h.csv"
data_path = f"/N/slate/trihnguy/ncep_netcdf3_1999_2022_small/tc_{LEADTIME}h.csv"
train_path = data_path.replace('.csv', '_train.csv')
val_path = data_path.replace('.csv', '_val.csv')
test_path = data_path.replace('.csv', '_test.csv')
"""
subset = OrderedDict(
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
"""
'''
subset = OrderedDict(
    ugrdprs = [800, 200],
    vgrdprs = [800, 200],
    rhprs =  [750],
    capesfc=True,
    tmpsfc = True)
    '''
"""
subset = dict(
    ugrdprs=[800, 200],
    vgrdprs=[800, 200],
    rhprs= [750],
    vvelprs=[500],
    tmpprs = [500],
    capesfc=True,
    tmpsfc=True,
    tmptrp=True,
    hgttrp=True)
    """
"""
data_shape = (41, 161, 13)
subset = dict(
    absvprs=None, # [900, 750],
    rhprs=None, # [750],
    tmpprs=None, # [900, 500],
    hgtprs=None, # [500],
    vvelprs=None, # [500],
    # ugrdprs=[800, 200],
    # vgrdprs=[800, 200],
    capesfc=None,
    tmpsfc=None,
)
"""
# data_shape = (41, 161, 38)
# subset = dict(
#     absvprs=[900, 800, 750, 500, 200],
#     rhprs=[900, 800, 750, 500, 200],
#     tmpprs=[900, 800, 750, 500, 200],
#     hgtprs=[900, 800, 750, 500, 200],
#     vvelprs=[900, 800, 750, 500, 200],
#     ugrdprs=[900, 800, 750, 500, 200],
#     vgrdprs=[900, 800, 750, 500, 200],
# )
# data_shape = (41, 161, 37)
# subset = None
# data_shape = (41, 161, 135)
#data_shape = (41, 161, 13)

#data_shape =  (21,56, 15)
"""
subset = dict(
    ugrdprs=[800, 200],
    vgrdprs=[800, 200],
    rhprs= [750])
"""
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

# data_shape = (41, 81, 7)
# subset = dict(ugrdprs=[800, 200],
#     vgrdprs=[800, 200],
#     rhprs= [750],
#     vvelprs=[500],
#     tmpprs = [500],
#     capesfc = True,
#     tmpsfc=True
#     )
# data_shape = (41, 81, 9)


subset = dict(
    absvprs= [900, 750],
    rhprs=[750],
    tmpprs=[900, 500],
    hgtprs= [500],
    vvelprs= [500],
    ugrdprs=[800, 200],
    vgrdprs=[800, 200],
    capesfc=True,
    tmpsfc=True,
)
data_shape = (41, 81, 13)
use_softmax = False
# -

# Create U-Net model with normalization layer.

input_layer = keras.Input(data_shape)
normalization_layer = preprocessing.Normalization()
model = unet.Unet(
    input_tensor=normalization_layer(input_layer),
    model_name='unet',
    classifier_activation='sigmoid' if not use_softmax else 'softmax',
    output_classes=1 if not use_softmax else 2,
    decoder_shortcut_mode='add',
    filters_block=[64, 128, 256, 512, 1024])
model.summary()

# +

# data_loader = ts_data.TropicalCycloneWithGridProbabilityDataLoader(
#     data_shape=data_shape,
#     tc_avg_radius_lat_deg=tc_avg_radius_lat_deg,
#     subset=subset,
#     softmax_output=use_softmax,
#     smooth_gt=True,
# )


# +
# data_loader._data_shape

# +
import pandas as pd

df = pd.read_csv(train_path)
df.head()
# -

df['Genesis'].sum()

# Then, we load the training and validation dataset.

# +
tc_avg_radius_lat_deg = 3
data_loader = ts_data.TropicalCycloneWithGridProbabilityDataLoader(
    data_shape=data_shape,
    tc_avg_radius_lat_deg=tc_avg_radius_lat_deg,
    subset=subset,
    softmax_output=use_softmax,
    smooth_gt=True,
)

print("data")
training = data_loader.load_dataset(
    train_path,
    batch_size=128,
    leadtimes=LEADTIME,
    shuffle=True,
    nonTCRatio=3,
)
print("training")
validation = data_loader.load_dataset(val_path, leadtimes=LEADTIME, batch_size=128)
# -

# After that, we will initialize the normalization layer,
# and compile the model.

features = training.map(lambda feature, _: feature)
#print(features[0])
normalization_layer.adapt(features)


# +
@hard_negative_mining
def hard_negative_mined_sigmoid_focal_loss(y_true, y_pred):
    fl = tfa.losses.SigmoidFocalCrossEntropy()
    return fl(y_true, y_pred)

@hard_negative_mining
def hard_negative_mined_binary_crossentropy_loss(y_true, y_pred):
    l = tf.keras.losses.BinaryCrossentropy(reduction=tf.keras.losses.Reduction.NONE)
    return l(y_true, y_pred)

def dice_loss(y_true, y_pred):
    y_true = tf.cast(y_true, tf.float32)
    # y_pred = tf.math.sigmoid(y_pred)
    numerator = 2 * tf.reduce_sum(y_true * y_pred)
    denominator = tf.reduce_sum(y_true + y_pred)

    return 1 - numerator / denominator

def combine_loss_funcs(*fns):
    def combined_loss(y_true, y_pred):
        return sum(f(y_true, y_pred) for f in fns)
    
    return combined_loss

model.compile(
    optimizer='adam',
    # loss=tf.keras.losses.BinaryCrossentropy(),
    # loss=combine_loss_funcs(hard_negative_mined_sigmoid_focal_loss, dice_loss),
    loss=dice_loss,
    # loss=hard_negative_mined_sigmoid_focal_loss,
    # loss=hard_negative_mined_binary_crossentropy_loss,
    metrics=[
        'binary_accuracy',
        keras.metrics.Recall(name='recall_score', class_id=1 if use_softmax else None),
        keras.metrics.Precision(name='precision_score', class_id=1 if use_softmax else None),
        tfm.CustomF1Score(name='f1_score', class_id=1 if use_softmax else None),
        bb.BBoxesIoUMetric(name='IoU', iou_threshold=0.2),
        #tfa.metrics.F1Score(num_classes=1, threshold=0.5),
        #tfm.PrecisionScore(from_logits=True),
        #tfm.F1Score(num_classes=1, from_logits=True, threshold=0.5),
    ])
# -

# Finally, we can train the model!

epochs = 100
history = model.fit(
    training,
    epochs=epochs,
    validation_data=validation,
    shuffle=True,
    callbacks=[
        keras.callbacks.TensorBoard(
            log_dir=f'outputs/{exp_name}_{runtime}_1st_board',
        ),
        keras.callbacks.ModelCheckpoint(
            filepath=f"outputs/{exp_name}_{runtime}_ckp_best_val",
            monitor='val_IoU',
            mode='max',
            save_best_only=True,
        ),
        keras.callbacks.EarlyStopping(
            monitor='val_IoU',
            mode='max',
            verbose=1,
            patience=20,
            restore_best_weights=True
        ),
    ]
)

# +
#print(history.history)
# -

plot.plot_training_history(history, "First stage training")

#for leadtime in [48]:
 #   #6, 12, 18, 24, 30, 36, 42,
  #  testing = data_loader.load_dataset(
  #      test_path,
   #     leadtimes=leadtime,
    #    batch_size=128
    #)
    #print(f'\n**** LEAD TIME: {leadtime}')
    #model.evaluate(testing)

testing = data_loader.load_dataset(
        test_path,
        leadtimes=LEADTIME,
        batch_size=128
    )
print(f'\n**** LEAD TIME: {LEADTIME}')
model.evaluate(testing)

# # Some Predictions

# +
import matplotlib.pyplot as plt # noqa
from mpl_toolkits.basemap import Basemap # noqa
import matplotlib.patches as patches # noqa
import numpy as np # noqa
import pandas as pd # noqa
import tc_formation.data.label as label # noqa
from tc_formation.data.data import load_observation_data_with_tc_probability # noqa
from tc_formation.plots import decorators, observations as plt_obs # noqa

size = '30'
params = {'legend.fontsize': size,
         'axes.labelsize': size,
         'axes.titlesize': size,
         'xtick.labelsize': size,
         'ytick.labelsize': size}
plt.rcParams.update(params)


@decorators._with_axes
@decorators._with_basemap
def plot_tc_occurence_prob(
        dataset: xr.Dataset,
        prob: np.ndarray,
        basemap: Basemap = None,
        *args, **kwargs):
    lats, longs = np.meshgrid(dataset['lon'], dataset['lat'])
    # TODO: changed from 0.0 -> 0.01
    prob[prob < 0.1] = np.nan
    cs = basemap.contourf(lats, longs, prob, cmap='Reds', levels=np.arange(0., 1.01, 0.05))
    basemap.colorbar(cs, "right", size="5%", pad="2%")
    
@decorators._with_axes
@decorators._with_basemap
def plot_SST(dataset, basemap=None, ax=None, **kwargs):
    lats, longs = np.meshgrid(dataset['lon'], dataset['lat'])
    cs = basemap.contour(lats, longs, dataset['tmpsfc'], levels=np.arange(270, 310, 2), cmap='Reds')
    ax.clabel(cs, inline=True, fontsize=18)
    
@decorators._with_axes
@decorators._with_basemap
def draw_rectangles(dataset: xr.Dataset, rectangles, basemap: Basemap = None, ax: plt.Axes = None, **kwargs):
    for rec in rectangles:
        min_lat = np.min(dataset['lat'])
        min_lon = np.min(dataset['lon'])
        rec = patches.Rectangle((min_lon + rec[0], min_lat + rec[1]), rec[2], rec[3], fill=False, **kwargs)
        ax.add_patch(rec)
    
def plot_stuffs(ds, pressure_level, ax):
    # Plot Relative Humidity
    plt_obs.plot_variablef(
        dataset=ds,
        variable='rhprs',
        pressure_level=pressure_level,
        cmap='Blues',
        ax=ax,
        contourf_kwargs=dict(levels=np.arange(0, 110, 5)))
    
    # Plot wind field.
    plt_obs.plot_wind(dataset=ds, pressure_level=pressure_level, ax=ax, skip=4)

    # Plot SST
    plot_SST(dataset=ds, ax=ax)

def plot_groundtruth_and_prediction(tc_df):
    iou = bb.BBoxesIoUMetric(iou_threshold=0.2)

    for _, row in tc_df.iterrows():
        dataset = xr.open_dataset(row['Path'])
        data, groundtruth = data_loader.load_single_data(row)
        gt_boxes = bb.extract_bounding_boxes(groundtruth)
        print('gt boxes', gt_boxes)
        
        prediction = model.predict([data])[0]
        pred_boxes = bb.extract_bounding_boxes(prediction)
        print('pred boxes', pred_boxes)
        
        iou.update_state([tf.cast(groundtruth, dtype=tf.float32)], [tf.cast(prediction, dtype=tf.float32)])
        print(f'IoU: {iou.result()}')
        iou.reset_states()
        
        if use_softmax:
            prediction = np.argmax(prediction, axis=-1)
        
        fig, axes = plt.subplots(nrows=4, figsize=(30, 36))
        plot_tc_occurence_prob(dataset=dataset, prob=np.squeeze(groundtruth), ax=axes[0])
#         axes[0].set_title(f"Groundtruth for date {row['Date']} for cyclogenesis on {row['First Observed']}")
        axes[0].set_title('a)', loc='left')
        plot_tc_occurence_prob(dataset=dataset, prob=np.squeeze(prediction), ax=axes[1])
#         axes[1].set_title(f"Prediction for date {row['Date']} for cyclogenesis on {row['First Observed']}")
        axes[1].set_title('b)', loc='left')
        # plt_obs.plot_wind(dataset=dataset, pressure_level=800, skip=4, ax=ax[0])
        ax = axes[2]
        plot_stuffs(dataset, pressure_level=850, ax=ax)
        draw_rectangles(dataset=dataset, rectangles=gt_boxes, ax=ax, edgecolor='lime', linewidth=4)
        draw_rectangles(dataset=dataset, rectangles=pred_boxes, ax=ax, edgecolor='coral', linewidth=4)
#         ax.set_title(f"SST, RH and Wind Field @ 850mb on date {row['Date']}")
        ax.set_title('c)', loc='left')

        # plt_obs.plot_wind(dataset=dataset, pressure_level=800, skip=4, ax=ax[1])
        ax = axes[3]
        plot_stuffs(dataset, pressure_level=500, ax=ax)
        draw_rectangles(dataset=dataset, rectangles=gt_boxes, ax=ax, edgecolor='lime', linewidth=4)
        draw_rectangles(dataset=dataset, rectangles=pred_boxes, ax=ax, edgecolor='coral', linewidth=4)
#         ax.set_title(f"SST, RH and Wind Field @ 500mb on date {row['Date']}")
        ax.set_title('d)', loc='left')
        
        if row['TC']:
            title = f"""Prediction on date {row['Date']} for tropical cyclone appearing on {row['First Observed']}"""
        else:
            title = f"Prediction on date {row['Date']}"
        fig.suptitle(title)
        fig.tight_layout()
        display(fig)
        plt.close(fig)
        
        print("=====\n=====\n====\n")


# -

# ## Train with TC

train_df = pd.read_csv(train_path)
train_with_tc_df = train_df[train_df['TC']].sample(2)
plot_groundtruth_and_prediction(train_with_tc_df)

# ## Test with TC

test_df = pd.read_csv(test_path)
test_with_tc_df = test_df[test_df['TC']].sample(2)
plot_groundtruth_and_prediction(test_with_tc_df)

# 12h leadtime
test_12h_df = label.load_label(test_path, leadtime=12)
test_with_tc_12h_df = test_12h_df[test_12h_df['TC']].sample(2)
plot_groundtruth_and_prediction(test_with_tc_12h_df)

# 24h leadtime
test_24h_df = label.load_label(train_path, leadtime=24)
print(test_24h_df.head())
test_with_tc_24h_df = test_24h_df[test_24h_df['TC']==True]
print("dat")
print(test_with_tc_24h_df)
#plot_groundtruth_and_prediction(test_with_tc_24h_df)

# 36h leadtime
test_36h_df = label.load_label(test_path, leadtime=36)
test_with_tc_36h_df = test_36h_df[test_36h_df['TC']].sample(2)
plot_groundtruth_and_prediction(test_with_tc_36h_df)

# ## Test without TC

test_without_tc_df = test_df[~test_df['TC']].sample(2)
plot_groundtruth_and_prediction(test_without_tc_df)

# 12h leadtime
test_without_tc_12h_df = test_12h_df[~test_12h_df['TC']].sample(2)
plot_groundtruth_and_prediction(test_without_tc_12h_df)

# 24h leadtime
test_without_tc_24h_df = test_24h_df[~test_24h_df['TC']].sample(2)
plot_groundtruth_and_prediction(test_without_tc_24h_df)

# 36h leadtime
test_without_tc_36h_df = test_36h_df[~test_36h_df['TC']].sample(2)
plot_groundtruth_and_prediction(test_without_tc_36h_df)

# + active=""
#
