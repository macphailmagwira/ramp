const fs = require('fs');
const path = require('path');

/**
 * Fetch OpenAPI schema from FastAPI
 */
async function fetchOpenAPISchema(apiBaseUrl) {
  const baseUrl = apiBaseUrl.replace(/\/$/, '');
  const paths = ['/openapi.json', '/docs/openapi.json'];
  
  for (const path of paths) {
    try {
      const url = `${baseUrl}${path}`;
      console.log(`   Trying: ${url}`);
      const data = await fetchUrl(url);
      return JSON.parse(data);
    } catch (error) {
      if (paths.indexOf(path) === paths.length - 1) throw error;
    }
  }
}

/**
 * Simple HTTP(S) GET request using built-in modules
 */
function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    const protocol = url.startsWith('https') ? require('https') : require('http');
    const req = protocol.get(url, { timeout: 10000 }, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode}: ${res.statusMessage}`));
        return;
      }
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

/**
 * Load OpenAPI schema from local file
 */
function loadOpenAPISchemaFromFile(filePath) {
  const fileContent = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(fileContent);
}

/**
 * Determine if endpoint is a query or mutation based on HTTP method
 */
function getOperationType(method) {
  return method.toLowerCase() === 'get' ? 'queries' : 'mutations';
}

/**
 * Convert FastAPI path parameter format to our format
 */
function convertPathFormat(path) {
  return path.replace(/\{(\w+)\}/g, '$$$1');
}

/**
 * Extract query parameters from OpenAPI operation
 */
function extractQueryParams(operation) {
  if (!operation.parameters) return [];
  return operation.parameters
    .filter(param => param.in === 'query')
    .map(param => param.name);
}

/**
 * Extract path parameters from path string
 */
function extractPathParams(path) {
  const matches = path.match(/\{(\w+)\}/g);
  if (!matches) return [];
  return matches.map(m => m.replace(/[{}]/g, ''));
}

/**
 * Determine if operation requires URL encoding for specific params
 */
function requiresUrlEncoding(pathParams) {
  const needsEncoding = ['email', 'cognito_sub'];
  return pathParams.filter(param => needsEncoding.includes(param));
}

/**
 * Generate resolver config from OpenAPI operation
 */
function generateResolverConfig(method, path, operation) {
  const config = {
    method: method.toUpperCase(),
    path: convertPathFormat(path),
    statusCodes: {}
  };
  
  if (operation.responses) {
    Object.entries(operation.responses).forEach(([code, response]) => {
      const statusCode = parseInt(code);
      if (statusCode >= 200 && statusCode < 300) {
        if (statusCode === 201) {
          config.statusCodes.success = 201;
        } else if (statusCode === 204) {
          config.statusCodes.success = 204;
          config.returnBoolean = true;
        } else {
          config.statusCodes.success = statusCode;
        }
      } else if (statusCode === 404) {
        config.statusCodes.notFound = 404;
      }
    });
  }
  
  if (operation.requestBody) config.hasBody = true;
  
  const queryParams = extractQueryParams(operation);
  if (queryParams.length > 0) config.queryParams = queryParams;
  
  const pathParams = extractPathParams(path);
  const urlEncodeParams = requiresUrlEncoding(pathParams);
  if (urlEncodeParams.length > 0) config.urlEncode = urlEncodeParams;
  
  return config;
}

/**
 * Convert OpenAPI tag to feature name
 */
function tagToFeatureName(tag) {
  return tag
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
}

/**
 * Convert operation ID or path to resolver name
 */
function generateResolverName(operationId, method, path) {
  if (operationId) {
    return operationId
      .replace(/Api.*$/i, '')
      .replace(/_/g, ' ')
      .split(' ')
      .filter(word => word.length > 0)
      .map((word, index) =>
        index === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1)
      )
      .join('');
  }
  const pathParts = path.split('/').filter(p => p && !p.startsWith('{'));
  const name = pathParts[pathParts.length - 1] || pathParts[pathParts.length - 2];
  return method.toLowerCase() + name.charAt(0).toUpperCase() + name.slice(1);
}

/**
 * Check if endpoint should be excluded
 */
function shouldExcludeEndpoint(operationId, path, summary, method, allExcludePatterns) {
  const normalizedOperationId = (operationId || '').toLowerCase();
  const normalizedPath = (path || '').toLowerCase();
  const normalizedSummary = (summary || '').toLowerCase();
  
  if (allExcludePatterns.some(pattern =>
    pattern.test(normalizedOperationId) ||
    pattern.test(normalizedPath) ||
    pattern.test(normalizedSummary)
  )) return true;
  
  if (path === '/' || path === '' || normalizedPath === '/api/v1' || normalizedPath === '/api/v1/') return true;
  
  const resolverName = generateResolverName(operationId, method, path).toLowerCase();
  const problematicNames = ['readroot','root','healthcheck','health','readrootget','getrootget','rootget','getroot'];
  if (problematicNames.includes(resolverName)) return true;
  
  return false;
}

/**
 * Parse OpenAPI schema and generate resolver configs grouped by tags
 */
function parseOpenAPISchema(schema, options = {}) {
  const featureResolvers = {};
  const { excludePatterns = [] } = options;
  
  const defaultExcludePatterns = [
    /health/i,
    /protected/i,
    /admin.*only/i,
    /read.*root/i,
    /root.*read/i,
    /\btest\b/i,
    /^\/?$/,
    /^\/api\/v\d+\/?$/i,
    /profile.*photo/i,
    /uploadProfilePhoto/i,
    /deleteProfilePhoto/i,
    /sketch/i,
    /uploadStyleSketches/i,
    /deleteStyleSketch/i,
    /deleteAllStyleSketches/i
  ];
  
  const allExcludePatterns = [...defaultExcludePatterns, ...excludePatterns];
  
  Object.entries(schema.paths).forEach(([path, pathItem]) => {
    Object.entries(pathItem).forEach(([method, operation]) => {
      if (!['get', 'post', 'put', 'patch', 'delete'].includes(method)) return;
      
      const operationId = operation.operationId || '';
      const summary = operation.summary || '';
      
      if (shouldExcludeEndpoint(operationId, path, summary, method, allExcludePatterns)) {
        console.log(`Skipping: ${operationId || path} (excluded)`);
        return;
      }
      
      const tag = operation.tags?.[0] || 'default';
      const featureName = tagToFeatureName(tag);
      
      if (!featureResolvers[featureName]) {
        featureResolvers[featureName] = { queries: {}, mutations: {} };
      }
      
      const resolverName = generateResolverName(operation.operationId, method, path);
      const operationType = getOperationType(method);
      const config = generateResolverConfig(method, path, operation);
      
      featureResolvers[featureName][operationType][resolverName] = config;
      console.log(`Added: ${operationType}.${resolverName}`);
    });
  });
  
  return featureResolvers;
}

/**
 * Generate JavaScript module content for shared-resolvers.js
 */
function generateSharedResolversModule(featureResolvers) {
  let output = `/**
 * AUTO-GENERATED FROM OPENAPI SCHEMA
 * DO NOT EDIT MANUALLY - Run generate-from-openapi.js to update
 */

// Helper to build API path with arguments
function buildPath(template, args) {
  let path = template;
  Object.keys(args).forEach(key => {
    if (key !== 'input') {
      path = path.replace(\`$\${key}\`, args[key]);
    }
  });
  return path;
}

function buildQueryString(args, paramNames) {
  const params = [];
  paramNames.forEach(name => {
    if (args[name] !== undefined && args[name] !== null) {
      params.push(\`\${name}=\${encodeURIComponent(args[name])}\`);
    }
  });
  return params.length > 0 ? \`?\${params.join('&')}\` : '';
}

`;

  function generateResolverObject(resolvers) {
    const lines = [];
    lines.push('{');
    lines.push('  queries: {');
    
    const queries = Object.entries(resolvers.queries);
    queries.forEach(([name, config], qIndex) => {
      lines.push(`    ${name}: {`);
      lines.push(`      method: "${config.method}",`);
      lines.push(`      path: "${config.path}",`);
      if (config.statusCodes) {
        lines.push('      statusCodes: {');
        Object.entries(config.statusCodes).forEach(([key, value]) => {
          lines.push(`        ${key}: ${value},`);
        });
        lines.push('      },');
      }
      if (config.hasBody) lines.push('      hasBody: true,');
      if (config.returnBoolean) lines.push('      returnBoolean: true,');
      if (config.queryParams && config.queryParams.length > 0) {
        lines.push(`      queryParams: [${config.queryParams.map(p => `"${p}"`).join(', ')}],`);
      }
      if (config.urlEncode && config.urlEncode.length > 0) {
        lines.push(`      urlEncode: [${config.urlEncode.map(p => `"${p}"`).join(', ')}],`);
      }
      lines.push(qIndex < queries.length - 1 ? '    },' : '    }');
    });
    
    lines.push('  },');
    lines.push('  mutations: {');
    
    const mutations = Object.entries(resolvers.mutations);
    mutations.forEach(([name, config], mIndex) => {
      lines.push(`    ${name}: {`);
      lines.push(`      method: "${config.method}",`);
      lines.push(`      path: "${config.path}",`);
      if (config.statusCodes) {
        lines.push('      statusCodes: {');
        Object.entries(config.statusCodes).forEach(([key, value]) => {
          lines.push(`        ${key}: ${value},`);
        });
        lines.push('      },');
      }
      if (config.hasBody) lines.push('      hasBody: true,');
      if (config.returnBoolean) lines.push('      returnBoolean: true,');
      if (config.queryParams && config.queryParams.length > 0) {
        lines.push(`      queryParams: [${config.queryParams.map(p => `"${p}"`).join(', ')}],`);
      }
      if (config.urlEncode && config.urlEncode.length > 0) {
        lines.push(`      urlEncode: [${config.urlEncode.map(p => `"${p}"`).join(', ')}],`);
      }
      lines.push(mIndex < mutations.length - 1 ? '    },' : '    }');
    });
    
    lines.push('  }');
    lines.push('}');
    return lines.join('\n');
  }

  // Generate feature resolver objects
  Object.entries(featureResolvers).forEach(([featureName, resolvers]) => {
    const camelCaseName = featureName
      .split('-')
      .map((word, i) => i === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
    output += `// ==========================================\n`;
    output += `// ${featureName.toUpperCase().replace(/-/g, ' ')} FEATURE\n`;
    output += `// ==========================================\n`;
    output += `const ${camelCaseName}Resolvers = ${generateResolverObject(resolvers)};\n\n`;
  });

  // Combined config
  output += `// ==========================================\n`;
  output += `// COMBINED CONFIG (for backward compatibility)\n`;
  output += `// ==========================================\n`;
  output += `const allFeatures = [\n`;
  output += Object.keys(featureResolvers).map(featureName => {
    const camelCaseName = featureName
      .split('-')
      .map((word, i) => i === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
    return `  ${camelCaseName}Resolvers`;
  }).join(',\n');
  output += `\n];\n\n`;

  output += `const resolverConfigs = {\n`;
  output += `  queries: {},\n`;
  output += `  mutations: {}\n`;
  output += `};\n\n`;

  output += `allFeatures.forEach(feature => {\n`;
  output += `  Object.assign(resolverConfigs.queries, feature.queries || {});\n`;
  output += `  Object.assign(resolverConfigs.mutations, feature.mutations || {});\n`;
  output += `});\n\n`;

  // Apollo resolver creator
  output += `// ==========================================\n`;
  output += `// APOLLO RESOLVERS GENERATOR\n`;
  output += `// ==========================================\n`;
  output += `function createApolloResolvers(fetchAPI, options = {}) {\n`;
  output += `  const { exclude = [] } = options;\n`;
  output += `  const resolvers = { Query: {}, Mutation: {} };\n\n`;

  // Query resolvers
  output += `  // Generate Query resolvers\n`;
  output += `  Object.entries(resolverConfigs.queries).forEach(([name, config]) => {\n`;
  output += `    if (exclude.includes(name)) return;\n\n`;
  output += `    resolvers.Query[name] = async (_, args, context) => {\n`;
  output += `      try {\n`;
  output += `        let apiPath = buildPath(config.path, args);\n`;
  output += `        if (config.queryParams) {\n`;
  output += `          apiPath += buildQueryString(args, config.queryParams);\n`;
  output += `        }\n`;
  output += `        return await fetchAPI(apiPath, {\n`;
  output += `          method: config.method,\n`;
  output += `          headers: { Authorization: context.authorization }\n`;
  output += `        });\n`;
  output += `      } catch (error) {\n`;
  output += `        console.error(\`Error in \${name}:\`, error);\n`;
  output += `        return null;\n`;
  output += `      }\n`;
  output += `    };\n`;
  output += `  });\n\n`;

  // Mutation resolvers — FIX IS HERE
  output += `  // Generate Mutation resolvers\n`;
  output += `  Object.entries(resolverConfigs.mutations).forEach(([name, config]) => {\n`;
  output += `    if (exclude.includes(name)) return;\n\n`;
  output += `    resolvers.Mutation[name] = async (_, args, context) => {\n`;
  output += `      try {\n`;
  output += `        let apiPath = buildPath(config.path, args);\n`;
  output += `        if (config.queryParams) {\n`;
  output += `          apiPath += buildQueryString(args, config.queryParams);\n`;
  output += `        }\n\n`;
  output += `        const fetchOptions = {\n`;
  output += `          method: config.method,\n`;
  output += `          headers: { Authorization: context.authorization }\n`;
  output += `        };\n\n`;
  output += `        if (config.hasBody) {\n`;
  output += `          fetchOptions.body = JSON.stringify(args.input);\n`;
  output += `        }\n\n`;
  output += `        // DELETE and other 204 ops: fire and return true on success\n`;
  output += `        if (config.returnBoolean) {\n`;
  output += `          await fetchAPI(apiPath, fetchOptions);\n`;
  output += `          return true;\n`;
  output += `        }\n\n`;
  output += `        return await fetchAPI(apiPath, fetchOptions);\n`;
  output += `      } catch (error) {\n`;
  output += `        console.error(\`Error in \${name}:\`, error);\n`;
  output += `        return false;\n`;
  output += `      }\n`;
  output += `    };\n`;
  output += `  });\n\n`;

  output += `  return resolvers;\n`;
  output += `}\n\n`;

  // Exports
  output += `// ==========================================\n`;
  output += `// EXPORTS\n`;
  output += `// ==========================================\n`;
  const featureExports = Object.keys(featureResolvers).map(featureName => {
    const camelCaseName = featureName
      .split('-')
      .map((word, i) => i === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
    return `  ${camelCaseName}Resolvers`;
  });
  output += `module.exports = {\n`;
  output += featureExports.join(',\n');
  output += `,\n  resolverConfigs,\n  createApolloResolvers,\n  buildPath,\n  buildQueryString\n};\n`;

  return output;
}

/**
 * Main function
 */
async function main() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║   OpenAPI Schema Generator for GraphQL Resolvers          ║');
  console.log('╚════════════════════════════════════════════════════════════╝');
  console.log('');

  const source = 'http://localhost:8000';
  console.log(`Fetching OpenAPI schema from: ${source}`);
  console.log('');

  const schema = await fetchOpenAPISchema(source);
  console.log(`Schema loaded successfully`);
  console.log(`API Title: ${schema.info?.title || 'Unknown'}`);
  console.log(`API Version: ${schema.info?.version || 'Unknown'}`);
  console.log('');

  let config = {};
  const configPath = path.join(__dirname, 'resolver-config.js');
  if (fs.existsSync(configPath)) {
    try {
      config = require(configPath);
      console.log('Loaded configuration from resolver-config.js');
    } catch (error) {
      console.log('Warning: Could not load resolver-config.js');
    }
  }

  console.log('Parsing OpenAPI schema...');
  console.log('');
  const featureResolvers = parseOpenAPISchema(schema, {
    excludePatterns: config.excludePatterns || []
  });

  console.log('');
  console.log('Discovered features:');
  Object.entries(featureResolvers).forEach(([featureName, resolvers]) => {
    const queryCount = Object.keys(resolvers.queries).length;
    const mutationCount = Object.keys(resolvers.mutations).length;
    console.log(`  - ${featureName}: ${queryCount} queries, ${mutationCount} mutations`);
  });

  console.log('');
  console.log('Generating shared-resolvers.js...');
  const moduleContent = generateSharedResolversModule(featureResolvers);
  const outputPath = path.join(__dirname, 'shared-resolvers.js');
  fs.writeFileSync(outputPath, moduleContent);

  console.log(`Generated: ${outputPath}`);
  console.log('');
  console.log('Next steps:');
  console.log('  1. Review generated shared-resolvers.js');
  console.log('  2. Run: node generate-vtl-resolvers.js');
  console.log('  3. Run: terraform plan && terraform apply');
  console.log('');
}

if (require.main === module) {
  main().catch(error => {
    console.error('❌ Error:', error.message);
    process.exit(1);
  });
}

module.exports = {
  fetchOpenAPISchema,
  loadOpenAPISchemaFromFile,
  parseOpenAPISchema,
  generateSharedResolversModule
};