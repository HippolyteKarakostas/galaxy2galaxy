"""Normalizing flow models learning the latent space of an existing Auto-Encoder
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import copy
import numpy as np

from tensor2tensor.layers import common_attention
from tensor2tensor.layers import common_hparams
from tensor2tensor.layers import common_layers
from tensor2tensor.layers import modalities
from tensor2tensor.utils import registry
from tensor2tensor.utils import t2t_model

from galaxy2galaxy.layers.flows import masked_autoregressive_conditional_template, real_nvp_conditional_template

import tensorflow as tf
import tensorflow_hub as hub
import tensorflow_probability as tfp
tfb = tfp.bijectors
tfd = tfp.distributions

class LatentFlow(t2t_model.T2TModel):
  """ Base class for latent flows

  This assumes that an already exported tensorflow hub autoencoder is provided
  in hparams.
  """

  def normalizing_flow(self, condition):
    """ Function building a normalizing flow, returned as a Tensorflow probability
    distribution
    """
    raise NotImplementedError

  def infer(self,
            features=None,
            decode_length=50,
            beam_size=1,
            top_beams=1,
            alpha=0.0,
            use_tpu=False):
    """ TODO: Switch to parent inference function
    """
    return self(features)[0]

  def body(self, features):
    hparams = self.hparams
    hparamsp = hparams.problem.get_hparams()

    x = features['inputs']
    cond = {k: features[k] for k in hparamsp.attributes}

    # Load the encoder and decoder modules
    encoder = hub.Module(hparams.encoder_module, trainable=False)

    latent_shape = encoder.get_output_info_dict()['default'].get_shape()[1:]
    latent_size = latent_shape[0].value*latent_shape[1].value*latent_shape[2].value
    code_shape = encoder.get_output_info_dict()['default'].get_shape()
    code_shape = [-1, code_shape[1].value, code_shape[2].value, code_shape[3].value]

    def get_flow(inputs, is_training=True):
      y = tf.concat([tf.expand_dims(inputs[k], axis=1) for k in hparamsp.attributes] ,axis=1)
      y = tf.layers.batch_normalization(y, name="y_norm", training=is_training)
      flow = self.normalizing_flow(y, latent_size)
      code = tf.reshape(flow.sample(tf.shape(y)[0]), code_shape)
      return code, flow

    if hparams.mode == tf.estimator.ModeKeys.PREDICT:
      # Export the latent flow alone
      def flow_module_spec():
        inputs = {k: tf.placeholder(tf.float32, shape=[None]) for k in hparamsp.attributes}
        code, _ = get_flow(inputs, is_training=False)
        hub.add_signature(inputs=inputs, outputs=code)
      flow_spec = hub.create_module_spec(flow_module_spec)
      flow = hub.Module(flow_spec, name='flow_module')
      hub.register_module_for_export(flow, "code_sampler")
      samples = flow(cond)
      return samples, {'loglikelihood': 0}

    # Encode the input image
    if hparams.encode_psf and 'psf' in features:
      code = encoder({'input':x, 'psf': features['psf']})
    else:
      code = encoder(x)

    with tf.variable_scope("flow_module"):
      samples, flow = get_flow(cond)
      loglikelihood = flow.log_prob(tf.layers.flatten(code))

    # This is the loglikelihood of a batch of images
    tf.summary.scalar('loglikelihood', tf.reduce_mean(loglikelihood))
    loss = - tf.reduce_mean(loglikelihood)
    return samples, {'training': loss}

@registry.register_model
class LatentMAF(LatentFlow):

  def normalizing_flow(self, conditioning, latent_size):
    """
    Normalizing flow based on Masked AutoRegressive Model.
    """
    hparams = self.hparams

    def init_once(x, name, trainable=False):
      return tf.get_variable(name, initializer=x, trainable=trainable)

    chain = []
    for i in range(hparams.num_hidden_layers):
      chain.append(tfb.MaskedAutoregressiveFlow(
                  shift_and_log_scale_fn=masked_autoregressive_conditional_template(
                  hidden_layers=[hparams.hidden_size, hparams.hidden_size],
                      conditional_tensor=conditioning, shift_only= i>2,
                      activation=common_layers.belu, name='maf%d'%i)))
      chain.append(tfb.Permute(permutation=init_once(
                           np.arange(latent_size)[::-1].astype("int32"),
                           name='permutation%d'%i)))
    chain = tfb.Chain(chain)

    flow = tfd.TransformedDistribution(distribution=tfd.MultivariateNormalDiag(loc=np.zeros(latent_size, dtype='float32'),
                                                                               scale_diag=np.ones(latent_size, dtype='float32')),
            bijector=chain)
    return flow


@registry.register_model
class LatentRealNVP(LatentFlow):

  def normalizing_flow(self, conditioning, latent_size):
    """
    Normalizing flow based on Masked AutoRegressive Model.
    """
    hparams = self.hparams

    def init_once(x, name, trainable=False):
      return tf.get_variable(name, initializer=x, trainable=trainable)

    chain = []
    for i in range(hparams.num_hidden_layers):
      chain.append(tfb.RealNVP(latent_size//2,
                  shift_and_log_scale_fn=real_nvp_conditional_template(
                  hidden_layers=[hparams.hidden_size, hparams.hidden_size],
                      conditional_tensor=conditioning,
                      shift_only=(i>hparams.num_hidden_layers//3),
                      log_scale_clip_gradient=True,
                      activation=common_layers.belu, name='maf%d'%i)))
      chain.append(tfb.Permute(permutation=init_once(
                           np.arange(latent_size)[::-1].astype("int32") if i % 2 ==0 else np.random.permutation(latent_size).astype("int32"),
                           name='permutation%d'%i)))
    chain = tfb.Chain(chain)

    flow = tfd.TransformedDistribution(distribution=tfd.MultivariateNormalDiag(loc=np.zeros(latent_size, dtype='float32'),
                                                                               scale_diag=np.ones(latent_size, dtype='float32')),
            bijector=chain)
    return flow


@registry.register_hparams
def latent_flow():
  """Basic autoencoder model."""
  hparams = common_hparams.basic_params1()
  hparams.optimizer = "adam"
  hparams.learning_rate_constant = 0.0002
  hparams.learning_rate_warmup_steps = 500
  hparams.learning_rate_schedule = "constant * linear_warmup"
  hparams.label_smoothing = 0.0
  hparams.batch_size = 128
  hparams.hidden_size = 256
  hparams.num_hidden_layers = 4
  hparams.initializer = "uniform_unit_scaling"
  hparams.initializer_gain = 1.0
  hparams.weight_decay = 0.0
  hparams.kernel_height = 4
  hparams.kernel_width = 4
  hparams.dropout = 0.0

  # hparams specifying the encoder
  hparams.add_hparam("encoder_module", "") # This needs to be overriden

  # hparams related to the PSF
  hparams.add_hparam("encode_psf", True) # Should we use the PSF at the encoder

  return hparams


@registry.register_hparams
def latent_flow_larger():
  """Basic autoencoder model."""
  hparams = common_hparams.basic_params1()
  hparams.optimizer = "adam"
  hparams.learning_rate_constant = 0.1
  hparams.learning_rate_warmup_steps = 1000
  hparams.learning_rate_schedule = "constant * linear_warmup * rsqrt_decay"
  hparams.label_smoothing = 0.0
  hparams.batch_size = 256
  hparams.hidden_size = 256
  hparams.num_hidden_layers = 10
  hparams.initializer = "uniform_unit_scaling"
  hparams.initializer_gain = 1.0
  hparams.weight_decay = 0.0
  hparams.kernel_height = 4
  hparams.kernel_width = 4
  hparams.dropout = 0.0

  # hparams specifying the encoder
  hparams.add_hparam("encoder_module", "") # This needs to be overriden

  # hparams related to the PSF
  hparams.add_hparam("encode_psf", True) # Should we use the PSF at the encoder

  return hparams
