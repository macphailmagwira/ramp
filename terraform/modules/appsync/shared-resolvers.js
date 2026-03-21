/**
 * AUTO-GENERATED FROM OPENAPI SCHEMA
 * DO NOT EDIT MANUALLY - Run generate-from-openapi.js to update
 */

// Helper to build API path with arguments
function buildPath(template, args) {
  let path = template;
  Object.keys(args).forEach(key => {
    if (key !== 'input') {
      path = path.replace(`$${key}`, args[key]);
    }
  });
  return path;
}

function buildQueryString(args, paramNames) {
  const params = [];
  paramNames.forEach(name => {
    if (args[name] !== undefined && args[name] !== null) {
      params.push(`${name}=${encodeURIComponent(args[name])}`);
    }
  });
  return params.length > 0 ? `?${params.join('&')}` : '';
}

// ==========================================
// DATA UPLOAD SUITE FEATURE
// ==========================================
const dataUploadSuiteResolvers = {
  queries: {
  },
  mutations: {
    generatePresignedUrl: {
      method: "POST",
      path: "/api/v1/data-upload-suite/s3-upload/presigned-url",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    }
  }
};

// ==========================================
// USERS FEATURE
// ==========================================
const usersResolvers = {
  queries: {
    listUsers: {
      method: "GET",
      path: "/api/v1/users",
      statusCodes: {
        success: 200,
      },
      queryParams: ["factory_id", "tenant_id", "is_active"],
    },
    getUser: {
      method: "GET",
      path: "/api/v1/users/$user_id",
      statusCodes: {
        success: 200,
      },
    },
    getUserByEmail: {
      method: "GET",
      path: "/api/v1/users/email/$email",
      statusCodes: {
        success: 200,
      },
      urlEncode: ["email"],
    },
    getUserByCognitoSub: {
      method: "GET",
      path: "/api/v1/users/cognito/$cognito_sub",
      statusCodes: {
        success: 200,
      },
      urlEncode: ["cognito_sub"],
    }
  },
  mutations: {
    createUser: {
      method: "POST",
      path: "/api/v1/users",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    inviteUser: {
      method: "POST",
      path: "/api/v1/users/invite",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateUser: {
      method: "PATCH",
      path: "/api/v1/users/$user_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteUser: {
      method: "DELETE",
      path: "/api/v1/users/$user_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// USER ROLES FEATURE
// ==========================================
const userRolesResolvers = {
  queries: {
    listUserRoles: {
      method: "GET",
      path: "/api/v1/user-roles",
      statusCodes: {
        success: 200,
      },
      queryParams: ["user_id", "factory_id"],
    },
    getUserRole: {
      method: "GET",
      path: "/api/v1/user-roles/$role_id",
      statusCodes: {
        success: 200,
      },
    },
    getUserRoleByUserAndFactory: {
      method: "GET",
      path: "/api/v1/user-roles/user/$user_id/factory/$factory_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createUserRole: {
      method: "POST",
      path: "/api/v1/user-roles",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateUserRole: {
      method: "PATCH",
      path: "/api/v1/user-roles/$role_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteUserRole: {
      method: "DELETE",
      path: "/api/v1/user-roles/$role_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// REFERENCE DATA FEATURE
// ==========================================
const referenceDataResolvers = {
  queries: {
    getRoleTypes: {
      method: "GET",
      path: "/api/v1/reference/roles",
      statusCodes: {
        success: 200,
      },
    },
    getDepartmentTypes: {
      method: "GET",
      path: "/api/v1/reference/departments",
      statusCodes: {
        success: 200,
      },
    },
    getRoleDepartmentMappings: {
      method: "GET",
      path: "/api/v1/reference/role-department-mappings",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
  }
};

// ==========================================
// TENANTS FEATURE
// ==========================================
const tenantsResolvers = {
  queries: {
    getTenant: {
      method: "GET",
      path: "/api/v1/tenants/$tenant_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    provisionTenant: {
      method: "POST",
      path: "/api/v1/tenants",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateTenant: {
      method: "PATCH",
      path: "/api/v1/tenants/$tenant_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteTenant: {
      method: "DELETE",
      path: "/api/v1/tenants/$tenant_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// MACHINES FEATURE
// ==========================================
const machinesResolvers = {
  queries: {
    getGenericMachines: {
      method: "GET",
      path: "/api/v1/factories/machines/generic",
      statusCodes: {
        success: 200,
      },
    },
    getFactoryMachines: {
      method: "GET",
      path: "/api/v1/factories/machines/factory/$factory_id",
      statusCodes: {
        success: 200,
      },
    },
    getFactoryMachine: {
      method: "GET",
      path: "/api/v1/factories/machines/$machine_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createFactoryMachine: {
      method: "POST",
      path: "/api/v1/factories/machines",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    createGenericMachine: {
      method: "POST",
      path: "/api/v1/factories/machines/generic",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateFactoryMachine: {
      method: "PATCH",
      path: "/api/v1/factories/machines/$machine_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteFactoryMachine: {
      method: "DELETE",
      path: "/api/v1/factories/machines/$machine_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// FACTORIES FEATURE
// ==========================================
const factoriesResolvers = {
  queries: {
    getProcesses: {
      method: "GET",
      path: "/api/v1/factories/processes",
      statusCodes: {
        success: 200,
      },
    },
    getFactory: {
      method: "GET",
      path: "/api/v1/factories/$factory_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createFactory: {
      method: "POST",
      path: "/api/v1/factories",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateFactory: {
      method: "PATCH",
      path: "/api/v1/factories/$factory_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    }
  }
};

// ==========================================
// BUYERS FEATURE
// ==========================================
const buyersResolvers = {
  queries: {
    listBuyers: {
      method: "GET",
      path: "/api/v1/buyers/factory/$factory_id",
      statusCodes: {
        success: 200,
      },
    },
    getBuyer: {
      method: "GET",
      path: "/api/v1/buyers/$buyer_id",
      statusCodes: {
        success: 200,
      },
    },
    getBuyerContact: {
      method: "GET",
      path: "/api/v1/buyers/contacts/$contact_id",
      statusCodes: {
        success: 200,
      },
    },
    listBrands: {
      method: "GET",
      path: "/api/v1/buyers/factories/$factory_id/brands",
      statusCodes: {
        success: 200,
      },
    },
    getBrand: {
      method: "GET",
      path: "/api/v1/buyers/brands/$brand_id",
      statusCodes: {
        success: 200,
      },
    },
    getSizeProfile: {
      method: "GET",
      path: "/api/v1/buyers/size-profiles/$profile_id",
      statusCodes: {
        success: 200,
      },
    },
    getSize: {
      method: "GET",
      path: "/api/v1/buyers/sizes/$size_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createBuyer: {
      method: "POST",
      path: "/api/v1/buyers",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateBuyer: {
      method: "PATCH",
      path: "/api/v1/buyers/$buyer_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteBuyer: {
      method: "DELETE",
      path: "/api/v1/buyers/$buyer_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    createBuyerContact: {
      method: "POST",
      path: "/api/v1/buyers/contacts",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateBuyerContact: {
      method: "PATCH",
      path: "/api/v1/buyers/contacts/$contact_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteBuyerContact: {
      method: "DELETE",
      path: "/api/v1/buyers/contacts/$contact_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    createBrand: {
      method: "POST",
      path: "/api/v1/buyers/brands",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateBrand: {
      method: "PATCH",
      path: "/api/v1/buyers/brands/$brand_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteBrand: {
      method: "DELETE",
      path: "/api/v1/buyers/brands/$brand_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    createSizeProfile: {
      method: "POST",
      path: "/api/v1/buyers/size-profiles",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateSizeProfile: {
      method: "PATCH",
      path: "/api/v1/buyers/size-profiles/$profile_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteSizeProfile: {
      method: "DELETE",
      path: "/api/v1/buyers/size-profiles/$profile_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    createSize: {
      method: "POST",
      path: "/api/v1/buyers/sizes",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    }
  }
};

// ==========================================
// SECTORS FEATURE
// ==========================================
const sectorsResolvers = {
  queries: {
    listSectorProcesses: {
      method: "GET",
      path: "/api/v1/sectors/processes",
      statusCodes: {
        success: 200,
      },
    },
    getSector: {
      method: "GET",
      path: "/api/v1/sectors/$sector_id",
      statusCodes: {
        success: 200,
      },
    },
    getFactorySectors: {
      method: "GET",
      path: "/api/v1/sectors/factory/$factory_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createSector: {
      method: "POST",
      path: "/api/v1/sectors",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateSector: {
      method: "PATCH",
      path: "/api/v1/sectors/$sector_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteSector: {
      method: "DELETE",
      path: "/api/v1/sectors/$sector_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// LINES FEATURE
// ==========================================
const linesResolvers = {
  queries: {
    getLine: {
      method: "GET",
      path: "/api/v1/lines/$line_id",
      statusCodes: {
        success: 200,
      },
    },
    getSectorLines: {
      method: "GET",
      path: "/api/v1/lines/sector/$sector_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createLine: {
      method: "POST",
      path: "/api/v1/lines",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateLine: {
      method: "PATCH",
      path: "/api/v1/lines/$line_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteLine: {
      method: "DELETE",
      path: "/api/v1/lines/$line_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// SHIFTS FEATURE
// ==========================================
const shiftsResolvers = {
  queries: {
    getFactoryShifts: {
      method: "GET",
      path: "/api/v1/shifts/factory/$factory_id",
      statusCodes: {
        success: 200,
      },
    },
    getLineShifts: {
      method: "GET",
      path: "/api/v1/shifts/line/$line_id",
      statusCodes: {
        success: 200,
      },
    },
    getShift: {
      method: "GET",
      path: "/api/v1/shifts/$shift_id",
      statusCodes: {
        success: 200,
      },
    },
    getShiftBreaks: {
      method: "GET",
      path: "/api/v1/shifts/breaks/$shift_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createShift: {
      method: "POST",
      path: "/api/v1/shifts",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateShift: {
      method: "PATCH",
      path: "/api/v1/shifts/$shift_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteShift: {
      method: "DELETE",
      path: "/api/v1/shifts/$shift_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    createBreak: {
      method: "POST",
      path: "/api/v1/shifts/breaks",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateBreak: {
      method: "PATCH",
      path: "/api/v1/shifts/breaks/$break_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteBreak: {
      method: "DELETE",
      path: "/api/v1/shifts/breaks/$break_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// STYLES FEATURE
// ==========================================
const stylesResolvers = {
  queries: {
    getLineLayout: {
      method: "GET",
      path: "/api/v1/styles/line-layouts/$line_layout_id",
      statusCodes: {
        success: 200,
      },
    },
    listLineLayoutsByFactory: {
      method: "GET",
      path: "/api/v1/styles/factory/$factory_id/line-layouts",
      statusCodes: {
        success: 200,
      },
    },
    getOperations: {
      method: "GET",
      path: "/api/v1/styles/operations",
      statusCodes: {
        success: 200,
      },
    },
    getStyleReadinessStats: {
      method: "GET",
      path: "/api/v1/styles/factory/$factory_id/stats/readiness",
      statusCodes: {
        success: 200,
      },
    },
    listStyles: {
      method: "GET",
      path: "/api/v1/styles/factory/$factory_id",
      statusCodes: {
        success: 200,
      },
      queryParams: ["readiness"],
    },
    getStyle: {
      method: "GET",
      path: "/api/v1/styles/$style_id",
      statusCodes: {
        success: 200,
      },
    },
    getStyleProfile: {
      method: "GET",
      path: "/api/v1/styles/$style_id/profile",
      statusCodes: {
        success: 200,
      },
    },
    getStyleBulletin: {
      method: "GET",
      path: "/api/v1/styles/$style_id/bulletin",
      statusCodes: {
        success: 200,
      },
    },
    getStyleSummary: {
      method: "GET",
      path: "/api/v1/styles/$style_id/stats/summary",
      statusCodes: {
        success: 200,
      },
    },
    getRelatedStyles: {
      method: "GET",
      path: "/api/v1/styles/$style_id/related/styles",
      statusCodes: {
        success: 200,
      },
    },
    getRelatedOrders: {
      method: "GET",
      path: "/api/v1/styles/$style_id/related/orders",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createLineLayout: {
      method: "POST",
      path: "/api/v1/styles/line-layouts",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateLineLayout: {
      method: "PATCH",
      path: "/api/v1/styles/line-layouts/$line_layout_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteLineLayout: {
      method: "DELETE",
      path: "/api/v1/styles/line-layouts/$line_layout_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    deleteStationsByLineLayout: {
      method: "DELETE",
      path: "/api/v1/styles/line-layouts/$line_layout_id/stations",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    updateStation: {
      method: "PATCH",
      path: "/api/v1/styles/stations/$station_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteStation: {
      method: "DELETE",
      path: "/api/v1/styles/stations/$station_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    createStyle: {
      method: "POST",
      path: "/api/v1/styles",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateStyle: {
      method: "PATCH",
      path: "/api/v1/styles/$style_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteStyle: {
      method: "DELETE",
      path: "/api/v1/styles/$style_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    bulkCreateBulletinBreakdown: {
      method: "POST",
      path: "/api/v1/styles/bulletin/breakdown",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    bulkDeleteBulletinBreakdowns: {
      method: "DELETE",
      path: "/api/v1/styles/bulletin/breakdown",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    bulkUpdateBulletinBreakdown: {
      method: "PATCH",
      path: "/api/v1/styles/bulletin/breakdown",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    createMaterial: {
      method: "POST",
      path: "/api/v1/styles/materials",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    updateMaterial: {
      method: "PATCH",
      path: "/api/v1/styles/materials/$material_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteMaterial: {
      method: "DELETE",
      path: "/api/v1/styles/materials/$material_id",
      statusCodes: {
        success: 200,
      },
    }
  }
};

// ==========================================
// DEVICES FEATURE
// ==========================================
const devicesResolvers = {
  queries: {
    getDevice: {
      method: "GET",
      path: "/api/v1/devices/$device_id",
      statusCodes: {
        success: 200,
      },
    },
    getDevicesByFactory: {
      method: "GET",
      path: "/api/v1/devices/factory/$factory_id",
      statusCodes: {
        success: 200,
      },
    },
    getDevicesBySector: {
      method: "GET",
      path: "/api/v1/devices/sector/$sector_id",
      statusCodes: {
        success: 200,
      },
    },
    getDevicesByLine: {
      method: "GET",
      path: "/api/v1/devices/line/$line_id",
      statusCodes: {
        success: 200,
      },
    },
    getDevicesByStatus: {
      method: "GET",
      path: "/api/v1/devices/factory/$factory_id/status/$operational_status",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createDevice: {
      method: "POST",
      path: "/api/v1/devices",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateDevice: {
      method: "PATCH",
      path: "/api/v1/devices/$device_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteDevice: {
      method: "DELETE",
      path: "/api/v1/devices/$device_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    updateDeviceOperationalStatus: {
      method: "PATCH",
      path: "/api/v1/devices/$device_id/operational-status",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    reassignDevice: {
      method: "PATCH",
      path: "/api/v1/devices/$device_id/reassign",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    }
  }
};

// ==========================================
// ORDERS FEATURE
// ==========================================
const ordersResolvers = {
  queries: {
    listOrders: {
      method: "GET",
      path: "/api/v1/orders",
      statusCodes: {
        success: 200,
      },
    },
    getOrder: {
      method: "GET",
      path: "/api/v1/orders/$order_id",
      statusCodes: {
        success: 200,
      },
    },
    getOrdersByStatus: {
      method: "GET",
      path: "/api/v1/orders/status/$status",
      statusCodes: {
        success: 200,
      },
    },
    getOrdersByFactory: {
      method: "GET",
      path: "/api/v1/orders/factory/$factory_id",
      statusCodes: {
        success: 200,
      },
    },
    getOrdersByBuyer: {
      method: "GET",
      path: "/api/v1/orders/buyer/$buyer_id",
      statusCodes: {
        success: 200,
      },
    },
    getOrdersCountByStatus: {
      method: "GET",
      path: "/api/v1/orders/analytics/orders-by-status/$factory_id",
      statusCodes: {
        success: 200,
      },
    },
    getOrderStyle: {
      method: "GET",
      path: "/api/v1/orders/styles/$order_style_id",
      statusCodes: {
        success: 200,
      },
    },
    getDestinationAssociation: {
      method: "GET",
      path: "/api/v1/orders/destinations/$order_destination_style_id",
      statusCodes: {
        success: 200,
      },
    },
    getCosting: {
      method: "GET",
      path: "/api/v1/orders/costings/$costing_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createOrder: {
      method: "POST",
      path: "/api/v1/orders",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateOrder: {
      method: "PATCH",
      path: "/api/v1/orders/$order_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteOrder: {
      method: "DELETE",
      path: "/api/v1/orders/$order_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    createOrderStyle: {
      method: "POST",
      path: "/api/v1/orders/$order_id/styles",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateOrderStyle: {
      method: "PATCH",
      path: "/api/v1/orders/styles/$order_style_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteOrderStyle: {
      method: "DELETE",
      path: "/api/v1/orders/styles/$order_style_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    addDestinationToOrderStyle: {
      method: "POST",
      path: "/api/v1/orders/styles/$order_style_id/destinations",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateDestinationOnOrderStyle: {
      method: "PATCH",
      path: "/api/v1/orders/destinations/$order_destination_style_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteDestinationFromOrderStyle: {
      method: "DELETE",
      path: "/api/v1/orders/destinations/$order_destination_style_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    addCostingsToOrderStyle: {
      method: "POST",
      path: "/api/v1/orders/styles/$order_style_id/costings",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateCosting: {
      method: "PATCH",
      path: "/api/v1/orders/costings/$costing_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteCosting: {
      method: "DELETE",
      path: "/api/v1/orders/costings/$costing_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// QC DATA COLLECTION FEATURE
// ==========================================
const qcDataCollectionResolvers = {
  queries: {
    getQcEvent: {
      method: "GET",
      path: "/api/v1/qc-data-collection/events/$event_id",
      statusCodes: {
        success: 200,
      },
    },
    getBatchEvents: {
      method: "GET",
      path: "/api/v1/qc-data-collection/events/batch/$batch_id",
      statusCodes: {
        success: 200,
      },
      queryParams: ["limit", "offset"],
    },
    getPlanEvents: {
      method: "GET",
      path: "/api/v1/qc-data-collection/events/plan/$plan_id",
      statusCodes: {
        success: 200,
      },
      queryParams: ["limit", "offset"],
    },
    listQcEvents: {
      method: "GET",
      path: "/api/v1/qc-data-collection/events",
      statusCodes: {
        success: 200,
      },
      queryParams: ["start_date", "end_date", "plan_id", "qc_categorisation", "device_id", "limit", "offset"],
    }
  },
  mutations: {
    submitQcEventBatch: {
      method: "POST",
      path: "/api/v1/qc-data-collection/events/batch",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    }
  }
};

// ==========================================
// QC DEFECT COLLECTION FEATURE
// ==========================================
const qcDefectCollectionResolvers = {
  queries: {
    getQcDefect: {
      method: "GET",
      path: "/api/v1/qc-defects-collection/defects/$defect_id",
      statusCodes: {
        success: 200,
      },
    },
    getBatchDefects: {
      method: "GET",
      path: "/api/v1/qc-defects-collection/defects/batch/$batch_id",
      statusCodes: {
        success: 200,
      },
      queryParams: ["limit", "offset"],
    },
    getParentEventDefects: {
      method: "GET",
      path: "/api/v1/qc-defects-collection/defects/parent/$parent_qc_event_id",
      statusCodes: {
        success: 200,
      },
      queryParams: ["limit", "offset"],
    },
    listQcDefects: {
      method: "GET",
      path: "/api/v1/qc-defects-collection/defects",
      statusCodes: {
        success: 200,
      },
      queryParams: ["start_date", "end_date", "defect_type", "parent_qc_event_id", "limit", "offset"],
    }
  },
  mutations: {
    submitQcDefectBatch: {
      method: "POST",
      path: "/api/v1/qc-defects-collection/defects/batch",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    }
  }
};

// ==========================================
// PRODUCTION PLANS FEATURE
// ==========================================
const productionPlansResolvers = {
  queries: {
    getProductionPlans: {
      method: "GET",
      path: "/api/v1/production-plans/factory/$factory_id",
      statusCodes: {
        success: 200,
      },
      queryParams: ["status"],
    },
    getCapacityUtilizationSummary: {
      method: "GET",
      path: "/api/v1/production-plans/factory/$factory_id/capacity-utilization",
      statusCodes: {
        success: 200,
      },
      queryParams: ["start_date", "end_date", "sectors", "lines", "buyers", "styles", "order_statuses", "orders"],
    },
    getProductionPlan: {
      method: "GET",
      path: "/api/v1/production-plans/$plan_id",
      statusCodes: {
        success: 200,
      },
    },
    getProductionPlanProfile: {
      method: "GET",
      path: "/api/v1/production-plans/$plan_id/profile",
      statusCodes: {
        success: 200,
      },
    },
    getProductionPlanSummary: {
      method: "GET",
      path: "/api/v1/production-plans/$plan_id/summary",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createProductionPlan: {
      method: "POST",
      path: "/api/v1/production-plans",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateProductionPlan: {
      method: "PATCH",
      path: "/api/v1/production-plans/$plan_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteProductionPlan: {
      method: "DELETE",
      path: "/api/v1/production-plans/$plan_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// LINE CHANGEOVER EVENTS FEATURE
// ==========================================
const lineChangeoverEventsResolvers = {
  queries: {
    getLineChangeoverEvent: {
      method: "GET",
      path: "/api/v1/line-changeover-events/$event_id",
      statusCodes: {
        success: 200,
      },
    },
    getLineChangeoverEventsByLine: {
      method: "GET",
      path: "/api/v1/line-changeover-events/line/$line_id",
      statusCodes: {
        success: 200,
      },
    },
    getLineChangeoverEventsByProductionPlan: {
      method: "GET",
      path: "/api/v1/line-changeover-events/production-plan/$production_plan_id",
      statusCodes: {
        success: 200,
      },
    },
    getLineChangeoverEventsByBatch: {
      method: "GET",
      path: "/api/v1/line-changeover-events/batch/$batch_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createLineChangeoverEvent: {
      method: "POST",
      path: "/api/v1/line-changeover-events",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateLineChangeoverEvent: {
      method: "PATCH",
      path: "/api/v1/line-changeover-events/$event_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteLineChangeoverEvent: {
      method: "DELETE",
      path: "/api/v1/line-changeover-events/$event_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    },
    submitLineChangeoverEventBatch: {
      method: "POST",
      path: "/api/v1/line-changeover-events/batch",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    }
  }
};

// ==========================================
// DEVICE EVENTS FEATURE
// ==========================================
const deviceEventsResolvers = {
  queries: {
    getLineChangeoverDeviceEvent: {
      method: "GET",
      path: "/api/v1/line-changeover-device-events/$record_id",
      statusCodes: {
        success: 200,
      },
    },
    getDeviceEventsByChangeoverEvent: {
      method: "GET",
      path: "/api/v1/line-changeover-device-events/changeover-event/$changeover_event_id",
      statusCodes: {
        success: 200,
      },
    },
    getDeviceEventsByDevice: {
      method: "GET",
      path: "/api/v1/line-changeover-device-events/device/$device_id",
      statusCodes: {
        success: 200,
      },
    }
  },
  mutations: {
    createLineChangeoverDeviceEvent: {
      method: "POST",
      path: "/api/v1/line-changeover-device-events",
      statusCodes: {
        success: 201,
      },
      hasBody: true,
    },
    updateLineChangeoverDeviceEvent: {
      method: "PATCH",
      path: "/api/v1/line-changeover-device-events/$record_id",
      statusCodes: {
        success: 200,
      },
      hasBody: true,
    },
    deleteLineChangeoverDeviceEvent: {
      method: "DELETE",
      path: "/api/v1/line-changeover-device-events/$record_id",
      statusCodes: {
        success: 204,
      },
      returnBoolean: true,
    }
  }
};

// ==========================================
// COMBINED CONFIG (for backward compatibility)
// ==========================================
const allFeatures = [
  dataUploadSuiteResolvers,
  usersResolvers,
  userRolesResolvers,
  referenceDataResolvers,
  tenantsResolvers,
  machinesResolvers,
  factoriesResolvers,
  buyersResolvers,
  sectorsResolvers,
  linesResolvers,
  shiftsResolvers,
  stylesResolvers,
  devicesResolvers,
  ordersResolvers,
  qcDataCollectionResolvers,
  qcDefectCollectionResolvers,
  productionPlansResolvers,
  lineChangeoverEventsResolvers,
  deviceEventsResolvers
];

const resolverConfigs = {
  queries: {},
  mutations: {}
};

allFeatures.forEach(feature => {
  Object.assign(resolverConfigs.queries, feature.queries || {});
  Object.assign(resolverConfigs.mutations, feature.mutations || {});
});

// ==========================================
// APOLLO RESOLVERS GENERATOR
// ==========================================
function createApolloResolvers(fetchAPI, options = {}) {
  const { exclude = [] } = options;
  const resolvers = { Query: {}, Mutation: {} };

  // Generate Query resolvers
  Object.entries(resolverConfigs.queries).forEach(([name, config]) => {
    if (exclude.includes(name)) return;

    resolvers.Query[name] = async (_, args, context) => {
      try {
        let apiPath = buildPath(config.path, args);
        if (config.queryParams) {
          apiPath += buildQueryString(args, config.queryParams);
        }
        return await fetchAPI(apiPath, {
          method: config.method,
          headers: { Authorization: context.authorization }
        });
      } catch (error) {
        console.error(`Error in ${name}:`, error);
        return null;
      }
    };
  });

  // Generate Mutation resolvers
  Object.entries(resolverConfigs.mutations).forEach(([name, config]) => {
    if (exclude.includes(name)) return;

    resolvers.Mutation[name] = async (_, args, context) => {
      try {
        let apiPath = buildPath(config.path, args);
        if (config.queryParams) {
          apiPath += buildQueryString(args, config.queryParams);
        }

        const fetchOptions = {
          method: config.method,
          headers: { Authorization: context.authorization }
        };

        if (config.hasBody) {
          fetchOptions.body = JSON.stringify(args.input);
        }

        // DELETE and other 204 ops: fire and return true on success
        if (config.returnBoolean) {
          await fetchAPI(apiPath, fetchOptions);
          return true;
        }

        return await fetchAPI(apiPath, fetchOptions);
      } catch (error) {
        console.error(`Error in ${name}:`, error);
        return false;
      }
    };
  });

  return resolvers;
}

// ==========================================
// EXPORTS
// ==========================================
module.exports = {
  dataUploadSuiteResolvers,
  usersResolvers,
  userRolesResolvers,
  referenceDataResolvers,
  tenantsResolvers,
  machinesResolvers,
  factoriesResolvers,
  buyersResolvers,
  sectorsResolvers,
  linesResolvers,
  shiftsResolvers,
  stylesResolvers,
  devicesResolvers,
  ordersResolvers,
  qcDataCollectionResolvers,
  qcDefectCollectionResolvers,
  productionPlansResolvers,
  lineChangeoverEventsResolvers,
  deviceEventsResolvers,
  resolverConfigs,
  createApolloResolvers,
  buildPath,
  buildQueryString
};
