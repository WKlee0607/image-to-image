import gc
import argparse
import logging
from pathlib import Path

import yaml
from tqdm import tqdm
import matplotlib.pyplot as plt

import torch
from torch.utils.data import DataLoader

from torchmetrics import MeanAbsoluteError
from torchmetrics.regression import PearsonCorrCoef
from torchmetrics.image import PeakSignalNoiseRatio, StructuralSimilarityIndexMeasure

from networks import define_G
from pipeline import AlignedDataset


# Metrics ========================================================================
def calculate_metrics(model, loader, device, log_dir, binning=4, stage="Validation"):
    mae = MeanAbsoluteError().to(device)                  # 0.0 is best
    psnr = PeakSignalNoiseRatio().to(device)              # +inf is best
    ssim = StructuralSimilarityIndexMeasure().to(device)  # 1.0 is best
    pearson = PearsonCorrCoef().to(device)                # 1.0 is best
    
    maes = []
    psnrs = []
    ssims = []
    pearsons = []

    avgpool2d = torch.nn.AvgPool2d(binning)
    maes_binning = []
    psnrs_binning = []
    ssims_binning = []
    pearsons_binning = []

    for i, (inputs, real_target) in enumerate(tqdm(loader, desc=stage)):
        inputs = inputs.to(device)
        real_target = real_target.to(device)
        fake_target = model(inputs)
        if i == 0:
            fig = val_dataset.create_figure(inputs[0], real_target[0], fake_target[0])
            fig.savefig(log_dir / f"{stage}_example.png")
            print(inputs.shape)
            print(real_target.shape)
            print(fake_target.shape)
        
        mae_value = mae(fake_target, real_target)
        pixel_to_pixel_cc = pearson(fake_target.flatten(), real_target.flatten())
        psnr_value = psnr(fake_target, real_target)
        ssim_value = ssim(fake_target, real_target)

        maes.append(mae_value.item())
        psnrs.append(psnr_value.item())
        ssims.append(ssim_value.item())
        pearsons.append(pixel_to_pixel_cc.item())

        mae.reset()
        pearson.reset()
        psnr.reset()
        ssim.reset()
        
        inputs_binning = avgpool2d(inputs)
        real_target_binning = avgpool2d(real_target)
        fake_target_binning = avgpool2d(fake_target)
        if i == 0:
            fig = val_dataset.create_figure(inputs[0], real_target_binning[0], fake_target_binning[0])
            fig.savefig(log_dir / f"{stage}_example_binning.png")
            print(inputs_binning.shape)
            print(real_target_binning.shape)
            print(fake_target_binning.shape)
            
        mae_value_binning = mae(fake_target_binning, real_target_binning)
        pixel_to_pixel_cc_binning = pearson(fake_target_binning.flatten(), real_target_binning.flatten())
        psnr_value_binning = psnr(fake_target_binning, real_target_binning)
        ssim_value_binning = ssim(fake_target_binning, real_target_binning)

        maes_binning.append(mae_value_binning.item())
        psnrs_binning.append(psnr_value_binning.item())
        ssims_binning.append(ssim_value_binning.item())
        pearsons_binning.append(pixel_to_pixel_cc_binning.item())
        
        mae.reset()
        psnr.reset()
        ssim.reset()
        pearson.reset()

        del inputs
        del real_target
        del fake_target
        del inputs_binning
        del real_target_binning
        del fake_target_binning

        gc.collect()
        torch.cuda.empty_cache()

    mae = sum(maes) / len(maes)
    psnr = sum(psnrs) / len(psnrs)
    ssim = sum(ssims) / len(ssims)
    pearson = sum(pearsons) / len(pearsons)

    mae_binning = sum(maes_binning) / len(maes_binning)
    psnr_binning = sum(psnrs_binning) / len(psnrs_binning)
    ssim_binning = sum(ssims_binning) / len(ssims_binning)
    pearson_binning = sum(pearsons_binning) / len(pearsons_binning)

    return {
        "MAE": mae,
        "PSNR": psnr,
        "SSIM": ssim,
        "Pearson": pearson,
        "MAE_binning": mae_binning,
        "PSNR_binning": psnr_binning,
        "SSIM_binning": ssim_binning,
        "Pearson_binning": pearson_binning
    }


# Main ===========================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--checkpoint", type=str, required=True)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    with open(args.config) as file:
        cfg = yaml.safe_load(file)
        if cfg.get('cfg') is not None:
            cfg = cfg['cfg']  
        data = cfg['data']
        params = cfg['params']

    G = define_G(cfg)
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=True)
    G.load_state_dict(checkpoint)
    G = G.to(device)

    val_dataset = AlignedDataset(
        input_dir=data['val']['input_dir'], 
        target_dir=data['val']['target_dir'],
        image_size=data['image_size'],
        ext=data['ext']
    )
    val_loader = DataLoader(
        val_dataset, 
        batch_size=data['val']['batch_size'], 
        shuffle=data['val']['shuffle'],
        num_workers=data['val']['num_workers'],
        pin_memory=data['val']['pin_memory'],
        drop_last=data['val']['drop_last']
    )

    test_dataset = AlignedDataset(
        input_dir=data['test']['input_dir'], 
        target_dir=data['test']['target_dir'],
        image_size=data['image_size'],
        ext=data['ext']
    )
    test_loader = DataLoader(
        test_dataset, 
        batch_size=data['test']['batch_size'], 
        shuffle=data['test']['shuffle'],
        num_workers=data['test']['num_workers'],
        pin_memory=data['test']['pin_memory'],
        drop_last=data['test']['drop_last']
    )

    log_dir = Path(args.checkpoint).parent.parent / "metrics"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.FileHandler(log_dir / "metric.log", "w"))

    with open(log_dir / "config.yaml", "w") as file:
        yaml.dump(args, file)

    binning = 4

    val_metrics = calculate_metrics(G, val_loader, device, log_dir, binning=binning, stage="Validation")
    with open(log_dir / "val_metrics.yaml", "w") as file:
        yaml.dump(val_metrics, file)
    logger.info(f"Validation MAE: {val_metrics['MAE']:.2f}")
    logger.info(f"Validation PSNR: {val_metrics['PSNR']:.2f}")
    logger.info(f"Validation SSIM: {val_metrics['SSIM']:.2f}")
    logger.info(f"Validation Pixel-to-Pixel Pearson CC: {val_metrics['Pearson']:.2f}")
    logger.info(f"Validation MAE (binning): {val_metrics['MAE_binning']:.2f}")
    logger.info(f"Validation PSNR (binning): {val_metrics['PSNR_binning']:.2f}")
    logger.info(f"Validation SSIM (binning): {val_metrics['SSIM_binning']:.2f}")
    logger.info(f"Validation Pixel-to-Pixel Pearson CC (binning): {val_metrics['Pearson_binning']:.2f}")

    test_metrics = calculate_metrics(G, test_loader, device, log_dir, binning=binning, stage="Test")
    with open(log_dir / "test_metrics.yaml", "w") as file:
        yaml.dump(test_metrics, file)
    logger.info(f"Test MAE: {test_metrics['MAE']:.2f}")
    logger.info(f"Test PSNR: {test_metrics['PSNR']:.2f}")
    logger.info(f"Test SSIM: {test_metrics['SSIM']:.2f}")
    logger.info(f"Test Pixel-to-Pixel Pearson CC: {test_metrics['Pearson']:.2f}")
    logger.info(f"Test MAE (binning): {test_metrics['MAE_binning']:.2f}")
    logger.info(f"Test PSNR (binning): {test_metrics['PSNR_binning']:.2f}")
    logger.info(f"Test SSIM (binning): {test_metrics['SSIM_binning']:.2f}")
    logger.info(f"Test Pixel-to-Pixel Pearson CC (binning): {test_metrics['Pearson_binning']:.2f}")





