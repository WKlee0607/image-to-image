from networks_default import Generator, Discriminator, weights_init
from Unet import R2AttU_Net, AttU_Net


# =============================================================================
def define_G(model_cfg):
    name_G = model_cfg['generator']['name']
    args = model_cfg['generator']['args']

    if name_G == 'default_generator':
        net_G = Generator(
            input_ch=args['input_ch'],
            target_ch=args['target_ch'],
            n_gf=args['n_gf'],
            n_downsample=args['n_downsample'],
            n_residual=args['n_residual'],
            norm_type=args['norm_type'],
            padding_type=args['padding_type'],
            trans_conv=args['trans_conv']
        )
        net_G.apply(weights_init)
    elif name_G == 'R2AttU_Net':
        net_G = R2AttU_Net(
            img_ch=args['input_ch'],
            output_ch=args['target_ch'],
            t=args['t']
        )
    elif name_G == 'AttU_Net':
        net_G = AttU_Net(
            img_ch=args['input_ch'],
            output_ch=args['target_ch']
        )
    else:
        raise NotImplementedError(f"Generator model name '{name_G}' is not implemented")
    
    return net_G


def define_D(model_cfg):
    name_D = model_cfg['discriminator']['name']
    args = model_cfg['discriminator']['args']

    if name_D == 'default_discriminator':
        net_D = Discriminator(
            input_ch=args['input_ch'],
            target_ch=args['target_ch'],
            n_df=args['n_df'],
            ch_balance=args['ch_balance'],
            n_D=args['n_D'],
        )
        net_D.apply(weights_init)
    else:
        raise NotImplementedError(f"Discriminator model name '{name_D}' is not implemented")
    
    return net_D


