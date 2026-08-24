/**
 * SASRIAKAL - Heatmap Overlay Renderer
 * Renders glowing red/amber gradient heatmaps over detected facial regions
 * with manipulation probability exceeding the threshold.
 */

class SASRIAKALHeatmapRenderer {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.threshold = options.threshold || 0.65;
    this.animationFrame = null;
    this.currentHeatmap = null;
    this.glowPhase = 0;
    this.fadeOpacity = 0;
    this.targetOpacity = 0;

    this.colorPalette = {
      low: { r: 255, g: 200, b: 0, a: 0.25 },    // amber
      mid: { r: 255, g: 120, b: 0, a: 0.45 },     // orange
      high: { r: 255, g: 40, b: 0, a: 0.7 },      // red
      critical: { r: 200, g: 0, b: 0, a: 0.85 },  // dark red
    };
  }

  /**
   * Update heatmap data from detection result.
   * @param {Array<{x: number, y: number, w: number, h: number, score: number, landmarks: Array}>} regions
   * @param {number} overallConfidence - Overall manipulation confidence [0, 1]
   */
  updateHeatmap(regions, overallConfidence) {
    this.currentHeatmap = regions;
    this.targetOpacity = overallConfidence >= this.threshold ? 0.9 : 0;

    if (!this.animationFrame) {
      this.animate();
    }
  }

  /**
   * Interpolate color based on manipulation score.
   */
  getColor(score) {
    const t = Math.max(0, Math.min(1, (score - this.threshold) / (1 - this.threshold)));
    const p = this.colorPalette;

    if (t < 0.33) {
      const lt = t / 0.33;
      return this.lerpColor(p.low, p.mid, lt);
    } else if (t < 0.66) {
      const lt = (t - 0.33) / 0.33;
      return this.lerpColor(p.mid, p.high, lt);
    } else {
      const lt = (t - 0.66) / 0.34;
      return this.lerpColor(p.high, p.critical, lt);
    }
  }

  lerpColor(c1, c2, t) {
    return {
      r: Math.round(c1.r + (c2.r - c1.r) * t),
      g: Math.round(c1.g + (c2.g - c1.g) * t),
      b: Math.round(c1.b + (c2.b - c1.b) * t),
      a: c1.a + (c2.a - c1.a) * t,
    };
  }

  /**
   * Main animation loop.
   */
  animate() {
    // Smooth opacity transition
    const opacityDiff = this.targetOpacity - this.fadeOpacity;
    if (Math.abs(opacityDiff) > 0.01) {
      this.fadeOpacity += opacityDiff * 0.15;
    } else {
      this.fadeOpacity = this.targetOpacity;
    }

    // Glow pulsation phase
    this.glowPhase += 0.04;
    const pulseIntensity = 0.7 + 0.3 * Math.sin(this.glowPhase);

    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    if (this.currentHeatmap && this.fadeOpacity > 0.01) {
      this.ctx.globalAlpha = this.fadeOpacity;

      this.currentHeatmap.forEach((region) => {
        const { x, y, w, h, score } = region;
        const color = this.getColor(score);

        // Radial gradient glow behind bounding box
        const cx = x + w / 2;
        const cy = y + h / 2;
        const radius = Math.max(w, h) * 0.8;

        const glow = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
        glow.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, ${color.a * pulseIntensity * 0.6})`);
        glow.addColorStop(0.5, `rgba(${color.r}, ${color.g}, ${color.b}, ${color.a * pulseIntensity * 0.3})`);
        glow.addColorStop(1, `rgba(${color.r}, ${color.g}, ${color.b}, 0)`);

        this.ctx.fillStyle = glow;
        this.ctx.fillRect(x - w * 0.3, y - h * 0.3, w * 1.6, h * 1.6);

        // Bounding box with glow
        this.ctx.shadowColor = `rgba(${color.r}, ${color.g}, ${color.b}, ${pulseIntensity})`;
        this.ctx.shadowBlur = 12 + 8 * pulseIntensity;
        this.ctx.strokeStyle = `rgba(${color.r}, ${color.g}, ${color.b}, ${0.8 * pulseIntensity})`;
        this.ctx.lineWidth = 2.5;
        this.ctx.strokeRect(x, y, w, h);

        // Inner gradient fill
        const innerGrad = this.ctx.createLinearGradient(x, y, x, y + h);
        innerGrad.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, ${color.a * 0.4 * pulseIntensity})`);
        innerGrad.addColorStop(1, `rgba(${color.r}, ${color.g}, ${color.b}, ${color.a * 0.1})`);
        this.ctx.fillStyle = innerGrad;
        this.ctx.fillRect(x, y, w, h);

        // Reset shadow
        this.ctx.shadowBlur = 0;

        // Confidence score label
        const labelY = y - 8 > 16 ? y - 8 : y + 16;
        this.ctx.fillStyle = `rgba(0, 0, 0, 0.6)`;
        this.ctx.fillRect(x - 2, labelY - 14, 70, 20);
        this.ctx.fillStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
        this.ctx.font = "bold 13px 'Courier New', monospace";
        this.ctx.fillText(
          `🎭 ${(score * 100).toFixed(1)}%`,
          x + 2,
          labelY
        );
      });

      this.ctx.globalAlpha = 1;
    }

    // Continue animation if transitioning or has active heatmap
    if (
      Math.abs(this.targetOpacity - this.fadeOpacity) > 0.01 ||
      this.currentHeatmap?.length > 0
    ) {
      this.animationFrame = requestAnimationFrame(() => this.animate());
    } else {
      this.animationFrame = null;
    }
  }

  destroy() {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
    }
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
}

// Export for use in content script context
if (typeof window !== "undefined") {
  window.SASRIAKALHeatmapRenderer = SASRIAKALHeatmapRenderer;
}
