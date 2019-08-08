# Galaxy2Galaxy

Galaxy2Galaxy, or G2G for short, is a library of models, datasets, and utilities to build generative models for astronomical images, based on the Tensor2Tensor library. Similarly to T2T, the goal of this project is to accelerate research in machine
learning models applied to astronomical image processing problems.

## Install

G2G can easily be installed using pip:
```
$ pip install --user git+https://github.com/EiffL/unagi.git # [Until proposed changes get merged into main unagi]
$ pip install --user git+https://github.com/ml4astro/galaxy2galaxy
```

## Usage

To generate the COSMOS 25.2 sample at native pixel scale and stamp size:

```bash
$ g2g-datagen --problem=img2img_cosmos --data_dir=data/img2img_cosmos
```
This uses GalSim to draw postage stamps and save them in TFRecord format which can then be used for training.

To  train an autoencoder with this data:
```bash
$ g2g-trainer --data_dir=data/img2img_cosmos --output_dir=training/cosmos_ae   --problem=img2img_cosmos --model=continuous_autoencoder_basic  --train_steps=2000  --eval_steps=100 --hparams_set=continuous_autoencoder_basic
```
