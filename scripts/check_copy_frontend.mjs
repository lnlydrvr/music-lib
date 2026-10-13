#!/usr/bin/env node
/** Find static notification literals whose callable binding is known. */
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";

const frontend = path.resolve(process.argv[2]);
const sourceRoot = path.resolve(process.argv[3]);
const files = process.argv.slice(4).map((file) => path.resolve(file));
const require = createRequire(path.join(frontend, "package.json"));
const ts = require("typescript");

const GLOBAL_NOTIFIERS = new Set(["alert", "confirm", "prompt"]);

function isToastModule(specifier) {
  return specifier === "../lib/toast" || specifier.endsWith("/lib/toast");
}

function addBinding(name, scope) {
  if (ts.isIdentifier(name)) {
    scope.names.add(name.text);
  } else if (ts.isObjectBindingPattern(name) || ts.isArrayBindingPattern(name)) {
    for (const element of name.elements) {
      if (ts.isBindingElement(element)) addBinding(element.name, scope);
    }
  }
}

function addVariableBindings(declarationList, scope) {
  const bindingScope = (declarationList.flags & ts.NodeFlags.BlockScoped) === 0 ? scope.varScope : scope;
  for (const declaration of declarationList.declarations) {
    addBinding(declaration.name, bindingScope);
  }
}

function collectScopeBindings(node, scope) {
  const statements = ts.isSourceFile(node) || ts.isBlock(node) || ts.isModuleBlock(node) ? node.statements : [];
  for (const statement of statements) {
    if (ts.isImportDeclaration(statement)) {
      const clause = statement.importClause;
      const specifier = ts.isStringLiteral(statement.moduleSpecifier) ? statement.moduleSpecifier.text : "";
      if (!clause) continue;
      if (clause.name) addBinding(clause.name, scope);
      for (const element of clause.namedBindings && ts.isNamedImports(clause.namedBindings) ? clause.namedBindings.elements : []) {
        addBinding(element.name, scope);
        if (isToastModule(specifier) && element.propertyName?.text === "toast" || isToastModule(specifier) && element.name.text === "toast") {
          scope.toasts.add(element.name.text);
        }
      }
    } else if (ts.isVariableStatement(statement)) {
      addVariableBindings(statement.declarationList, scope);
    } else if (ts.isFunctionDeclaration(statement) || ts.isClassDeclaration(statement) || ts.isEnumDeclaration(statement)) {
      addBinding(statement.name, scope);
    }
  }
}

function collectHoistedVarBindings(node, scope) {
  function visit(child) {
    if (child !== node && ts.isFunctionLike(child)) return;
    if (ts.isVariableDeclarationList(child) && (child.flags & ts.NodeFlags.BlockScoped) === 0) {
      addVariableBindings(child, scope);
    }
    ts.forEachChild(child, visit);
  }
  ts.forEachChild(node, visit);
}

function childScope(node, parent) {
  const scope = { names: new Set(), toasts: new Set(), parent, varScope: parent.varScope };
  if (ts.isFunctionLike(node)) {
    scope.varScope = scope;
    for (const parameter of node.parameters) {
      addBinding(parameter.name, scope);
    }
    if (node.body && ts.isBlock(node.body)) {
      collectScopeBindings(node.body, scope);
      collectHoistedVarBindings(node.body, scope);
    }
  } else if (ts.isBlock(node) || ts.isModuleBlock(node)) {
    collectScopeBindings(node, scope);
  } else if (ts.isForStatement(node) || ts.isForOfStatement(node) || ts.isForInStatement(node)) {
    if (node.initializer && ts.isVariableDeclarationList(node.initializer)) {
      addVariableBindings(node.initializer, scope);
    }
  }
  return scope;
}

function bindingKind(name, scope) {
  for (let current = scope; current; current = current.parent) {
    if (current.names.has(name)) return current.toasts.has(name) ? "toast" : "other";
  }
  return "global";
}

function isGlobalDialogProperty(expression, scope) {
  return ts.isPropertyAccessExpression(expression)
    && ts.isIdentifier(expression.expression)
    && (expression.expression.text === "window" || expression.expression.text === "globalThis")
    && GLOBAL_NOTIFIERS.has(expression.name.text)
    && bindingKind(expression.expression.text, scope) === "global";
}

function isNotificationCall(expression, scope) {
  return ts.isIdentifier(expression)
    ? GLOBAL_NOTIFIERS.has(expression.text) && bindingKind(expression.text, scope) !== "other"
    : isGlobalDialogProperty(expression, scope);
}

function notificationLiterals(file, source, relative) {
  const root = { names: new Set(), toasts: new Set(), parent: null, varScope: null };
  root.varScope = root;
  collectScopeBindings(source, root);
  collectHoistedVarBindings(source, root);
  const candidates = [];
  function visit(node, scope) {
    let current = scope;
    if (node !== source && (ts.isFunctionLike(node) || ts.isBlock(node) || ts.isModuleBlock(node)
      || ts.isForStatement(node) || ts.isForOfStatement(node) || ts.isForInStatement(node))) {
      current = childScope(node, scope);
    }
    if (ts.isCatchClause(node)) {
      current = { names: new Set(), toasts: new Set(), parent: scope, varScope: scope.varScope };
      if (node.variableDeclaration) addBinding(node.variableDeclaration.name, current);
    }
    if (ts.isCallExpression(node) && (isNotificationCall(node.expression, current) || (ts.isIdentifier(node.expression) && bindingKind(node.expression.text, current) === "toast"))) {
      const first = node.arguments[0];
      if (first && ts.isStringLiteralLike(first)) {
        const value = first.text;
        if (/[A-Za-zА-Яа-я]/.test(value)) candidates.push({ relative, line: source.getLineAndCharacterOfPosition(first.getStart(source)).line + 1, value });
      }
    }
    ts.forEachChild(node, (child) => visit(child, current));
  }
  visit(source, root);
  return candidates;
}

const candidates = files.flatMap((file) => {
  const text = ts.sys.readFile(file);
  if (text === undefined) throw new Error(`Cannot read ${file}`);
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  return notificationLiterals(file, source, path.relative(sourceRoot, file).split(path.sep).join("/"));
});
process.stdout.write(JSON.stringify(candidates));
