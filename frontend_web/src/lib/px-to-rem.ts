const ROOT_FONT_SIZE = 14;

function toFixed(number: number, precision: number) {
  const multiplier = Math.pow(10, precision + 1),
    wholeNumber = Math.floor(number * multiplier);
  return (Math.round(wholeNumber / 10) * 10) / multiplier;
}

export function pxToRem(
  px: number | string,
  rootValue: number = ROOT_FONT_SIZE,
  unitPrecision: number = 5,
  minPixelValue: number = 0.01
): string {
  if (!px) {
    return '';
  }
  const pixels = typeof px === 'string' ? parseFloat(px) : (px as number);
  if (pixels < minPixelValue) {
    return typeof px === 'string' ? px : `${px}px`;
  }
  const fixedVal = toFixed(pixels / rootValue, unitPrecision);
  return fixedVal + 'rem';
}

export function remToPx(
  rem: number | string,
  rootValue: number = ROOT_FONT_SIZE,
  unitPrecision: number = 5
): number {
  if (!rem) {
    return 0;
  }
  const value = typeof rem === 'string' ? parseFloat(rem) : (rem as number);
  return toFixed(value * rootValue, unitPrecision);
}
