import { MAX_EXPRESSION, PARAMETERS, type Parameter, type Parameters } from "./document";

type Variable = Parameter | "x";
type Operator = { args: 1 | 2; run: (left: number, right: number) => number };
type Operation = number | Variable | Operator;
export interface Expression {
  operations: Operation[];
  parameters: Parameter[];
}
const power: Operator = { args: 2, run: Math.pow };
const operators = new Map<string, [number, Operator]>([
  ["+", [10, { args: 2, run: (a,b) => a + b }]],
  ["-", [10, { args: 2, run: (a,b) => a - b }]],
  ["*", [20, { args: 2, run: (a,b) => a * b }]],
  ["/", [20, { args: 2, run: (a,b) => a / b }]],
  ["^", [30, power]],
]);
const functions = new Map<string, Operator>([
  ["sin", { args: 1, run: Math.sin }], ["cos", { args: 1, run: Math.cos }], ["pow", power],
]);
const negative: Operator = { args: 1, run: a => -a };

export class ExpressionError extends Error {
  constructor(message: string, readonly position: number) {
    super(`${message} (column ${position + 1})`);
  }
}

export function parseExpression(source: string): Expression {
  if ([...source].length > MAX_EXPRESSION) throw new ExpressionError("Expression too long", MAX_EXPRESSION);
  const tokens = Array.from(source.matchAll(/[0-9]+(?:\.[0-9]*)?|[a-zA-Z_][a-zA-Z_0-9]*|[^\s]/gu),
    match => ({ text: match[0], position: [...source.slice(0, match.index)].length }));
  tokens.push({ text: "", position: [...source].length });
  const operations: Operation[] = [];
  const used = new Set<string>();
  let index = 0;

  function expect(text: string) {
    const token = tokens[index];
    if (token.text !== text) throw new ExpressionError(`Expected '${text}'`, token.position);
    index++;
  }

  function read(minimum: number, depth: number) {
    const { text, position } = tokens[index++];
    if (depth > 32) throw new ExpressionError("Expression nested too deeply", position);
    if (text === "+" || text === "-") {
      read(30, depth + 1);
      if (text === "-") operations.push(negative);
    } else if (text === "(") {
      read(0, depth + 1);
      expect(")");
    } else if (/^[0-9]/.test(text)) {
      operations.push(Number(text));
    } else if (text === "x" || PARAMETERS.includes(text as Parameter)) {
      used.add(text);
      operations.push(text as Variable);
    } else {
      const fn = functions.get(text);
      if (!fn) throw new ExpressionError(text ? `Unexpected token '${text}'` : "Expected expression", position);
      expect("(");
      read(0, depth + 1);
      if (fn.args === 2) {
        expect(",");
        read(0, depth + 1);
      }
      expect(")");
      operations.push(fn);
    }
    for (let operator = operators.get(tokens[index].text);
      operator && operator[0] >= minimum; operator = operators.get(tokens[index].text)) {
      const { text } = tokens[index++];
      read(operator[0] + (text === "^" ? 0 : 1), depth + 1);
      operations.push(operator[1]);
    }
  }

  read(0, 0);
  const last = tokens[index];
  if (last.text) throw new ExpressionError(`Unexpected token '${last.text}'`, last.position);
  return { operations, parameters: PARAMETERS.filter(param => used.has(param)) };
}

export function evaluate(expression: Expression, x: number, params: Parameters): number | undefined {
  const stack: number[] = [];
  for (const operation of expression.operations) {
    let value: number;
    if (typeof operation === "number") value = operation;
    else if (typeof operation === "string") value = operation === "x" ? x : params[operation] ?? 1;
    else if (operation.args === 1) value = operation.run(stack.pop()!, 0);
    else {
      const right = stack.pop()!;
      value = operation.run(stack.pop()!, right);
    }
    if (!Number.isFinite(value)) return;
    stack.push(value);
  }
  return stack[0];
}

const cache = new Map<string, { expression: Expression; error?: never } | { expression?: never; error: string }>();
export function compile(text: string) {
  const cached = cache.get(text);
  if (cached) return cached;
  let result: (typeof cache extends Map<string, infer R> ? R : never);
  try { result = { expression: parseExpression(text) }; }
  catch (error) { result = { error: (error as Error).message }; }
  if (cache.size >= 128) cache.delete(cache.keys().next().value!);
  cache.set(text, result);
  return result;
}
