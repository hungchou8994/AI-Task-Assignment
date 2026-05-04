function decodeEscapedText(value: string): string {
  if (!value.includes("\\")) {
    return value;
  }

  // Only attempt decode when the string looks like it contains escaped content.
  if (!/\\u[0-9a-fA-F]{4}|\\[nrtbf"\\/]/.test(value)) {
    return value;
  }

  try {
    const jsonLiteral = `"${value
      .replace(/"/g, '\\"')
      .replace(/\r/g, "\\r")
      .replace(/\n/g, "\\n")
      .replace(/\t/g, "\\t")}"`;

    return JSON.parse(jsonLiteral) as string;
  } catch {
    return value;
  }
}

export function decodeEscapedTextDeep<T>(input: T): T {
  if (typeof input === "string") {
    return decodeEscapedText(input) as T;
  }

  if (Array.isArray(input)) {
    return input.map((item) => decodeEscapedTextDeep(item)) as T;
  }

  if (input && typeof input === "object") {
    const output: Record<string, unknown> = {};

    for (const [key, value] of Object.entries(input as Record<string, unknown>)) {
      output[key] = decodeEscapedTextDeep(value);
    }

    return output as T;
  }

  return input;
}
