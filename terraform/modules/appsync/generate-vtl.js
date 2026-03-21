const fs = require('fs');
const path = require('path');

const outputDir = __dirname;

// Define resolvers to skip (won't generate VTL files for these)
const SKIP_RESOLVERS = [
  'uploadProfilePhoto',
  'deleteProfilePhoto',
  // Add more resolver names here as needed
];

function toSnakeCase(str) {
  return str.replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '');
}

function generateVTLRequest(config) {
  let resourcePath = config.path;
  resourcePath = resourcePath.replace(/\$(\w+)/g, (match, arg) => {
    return `\${ctx.args.${arg}}`;
  });
  
  let vtlTemplate = '';
  
  if (config.queryParams && config.queryParams.length > 0) {
    // Generate VTL that builds query params dynamically
    vtlTemplate = `## Build query params dynamically
#set($queryParams = {})

`;
    
    config.queryParams.forEach(param => {
      vtlTemplate += `#if($ctx.args.${param} && $ctx.args.${param} != "")
  $util.qr($queryParams.put("${param}", $ctx.args.${param}))
#end

`;
    });
    
    const request = {
      version: "2018-05-29",
      method: config.method,
      resourcePath: resourcePath,
      params: {
        headers: {
          "Content-Type": "application/json",
          "Authorization": "$ctx.request.headers.authorization"
        },
        query: "$util.toJson($queryParams)"  // Use $util.toJson for proper quoting
      }
    };
    
    if (config.hasBody) {
      request.params.body = "$util.toJson($ctx.args.input)";
    }
    
    let json = JSON.stringify(request, null, 2);
    
    // Fix string replacements
    json = json.replace(/"\\\$\{ctx\.args\.(\w+)\}"/g, '"$ctx.args.$1"');
    json = json.replace(/"\$util\.toJson\(\$queryParams\)"/g, '$util.toJson($queryParams)');
    json = json.replace(/"\$ctx\.request\.headers\.authorization"/g, '"$ctx.request.headers.authorization"');
    json = json.replace(/"\$util\.toJson\(\$ctx\.args\.input\)"/g, '$util.toJson($ctx.args.input)');
    
    return vtlTemplate + json;
  } else {
    // No query params - simpler version
    const request = {
      version: "2018-05-29",
      method: config.method,
      resourcePath: resourcePath,
      params: {
        headers: {
          "Content-Type": "application/json",
          "Authorization": "$ctx.request.headers.authorization"
        }
      }
    };
    
    if (config.hasBody) {
      request.params.body = "$util.toJson($ctx.args.input)";
    }
    
    let json = JSON.stringify(request, null, 2);
    json = json.replace(/"\\\$\{ctx\.args\.(\w+)\}"/g, '"$ctx.args.$1"');
    json = json.replace(/"\$ctx\.request\.headers\.authorization"/g, '"$ctx.request.headers.authorization"');
    json = json.replace(/"\$util\.toJson\(\$ctx\.args\.input\)"/g, '$util.toJson($ctx.args.input)');
    
    return json;
  }
}

function generateVTLResponse(config) {
  const { success, notFound } = config.statusCodes;
  
  // For operations that return boolean (like DELETE)
  if (config.returnBoolean) {
    return `#if($ctx.result.statusCode == ${success})
  true
#else
  $util.error($ctx.result.body, "RequestError")
#end`;
  }
  
  // For operations that can return null on 404 (like GET by ID)
  if (notFound) {
    return `#if($ctx.result.statusCode == ${success})
  #if($ctx.result.body && $ctx.result.body.trim() != "")
    $util.toJson($util.parseJson($ctx.result.body))
  #else
    null
  #end
#elseif($ctx.result.statusCode == ${notFound})
  null
#else
  $util.error($ctx.result.body, "RequestError")
#end`;
  }
  
  // For standard operations (CREATE, UPDATE, LIST)
  return `#if($ctx.result.statusCode == ${success})
  #if($ctx.result.body && $ctx.result.body.trim() != "")
    $util.toJson($util.parseJson($ctx.result.body))
  #else
    $util.error("Empty response from API", "EmptyResponse")
  #end
#else
  $util.error($ctx.result.body, "RequestError")
#end`;
}

// Dynamically discover all features from shared-resolvers
const sharedResolvers = require('./shared-resolvers');

// Extract feature resolvers (any export ending with 'Resolvers')
const features = Object.entries(sharedResolvers)
  .filter(([key, value]) => key.endsWith('Resolvers') && typeof value === 'object')
  .map(([key, resolvers]) => {
    // Convert camelCase back to kebab-case for folder names
    // userManagementResolvers -> user-management
    const name = key
      .replace('Resolvers', '')
      .replace(/([A-Z])/g, '-$1')
      .toLowerCase()
      .replace(/^-/, '');
    
    return {
      name: name,
      resolvers: resolvers
    };
  });

console.log(`\nDiscovered ${features.length} features: ${features.map(f => f.name).join(', ')}\n`);

// Generate VTL files organized by feature
let totalGenerated = 0;
let totalSkipped = 0;

features.forEach(feature => {
  const featureName = feature.name;
  const resolvers = feature.resolvers;
  
  ['queries', 'mutations'].forEach(type => {
    const configs = resolvers[type] || {};
    
    if (Object.keys(configs).length === 0) return;
    
    // Create feature-based directory structure: resolvers/{feature}/{queries|mutations}
    const dir = path.join(outputDir, 'resolvers', featureName, type);
    
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    Object.entries(configs).forEach(([name, config]) => {
      // Skip if in skip list
      if (SKIP_RESOLVERS.includes(name)) {
        console.log(`⏭️  Skipped resolvers/${featureName}/${type}/${toSnakeCase(name)}_*.vtl`);
        totalSkipped += 2;
        return;
      }
      
      const snakeName = toSnakeCase(name);
      
      const requestPath = path.join(dir, `${snakeName}_request.vtl`);
      fs.writeFileSync(requestPath, generateVTLRequest(config));
      
      const responsePath = path.join(dir, `${snakeName}_response.vtl`);
      fs.writeFileSync(responsePath, generateVTLResponse(config));
      
      console.log(`✅ Generated resolvers/${featureName}/${type}/${snakeName}_*.vtl`);
      totalGenerated += 2;
    });
  });
});

console.log('\n' + '='.repeat(60));
console.log(`Successfully generated ${totalGenerated} VTL files!`);
if (totalSkipped > 0) {
  console.log(`Skipped ${totalSkipped} VTL files (in skip list)`);
}
console.log('='.repeat(60));

console.log('\nFolder structure:');
console.log('resolvers/');
features.forEach(feature => {
  console.log(`  ${feature.name}/`);
  if (feature.resolvers.queries && Object.keys(feature.resolvers.queries).length > 0) {
    console.log(`    queries/ (${Object.keys(feature.resolvers.queries).length} resolvers)`);
  }
  if (feature.resolvers.mutations && Object.keys(feature.resolvers.mutations).length > 0) {
    console.log(`    mutations/ (${Object.keys(feature.resolvers.mutations).length} resolvers)`);
  }
});

console.log('\nNext steps:');
console.log('  1. Review generated VTL files in resolvers/ directory');
console.log('  2. Run: terraform plan');
console.log('  3. Run: terraform apply');
console.log('');