import mongoose from 'mongoose';

// Don't check MONGODB_URI at module load time - check it when connectDB is called
// This allows the module to be loaded during build time without requiring env vars
function getMongoDBUri(): string {
  const MONGODB_URI = process.env.MONGODB_URI;
  
  if (!MONGODB_URI) {
    throw new Error('Please define the MONGODB_URI environment variable inside .env.local');
  }
  
  return MONGODB_URI;
}

interface MongooseCache {
  conn: typeof mongoose | null;
  promise: Promise<typeof mongoose> | null;
}

declare global {
  var mongoose: MongooseCache | undefined;
}

let cached: MongooseCache = global.mongoose || { conn: null, promise: null };

if (!global.mongoose) {
  global.mongoose = cached;
}

async function connectDB() {
  // Check for MONGODB_URI only when actually connecting (not at module load)
  const MONGODB_URI = getMongoDBUri();
  
  if (cached.conn) {
    return cached.conn;
  }

  if (!cached.promise) {
    const opts = {
      bufferCommands: false,
    };

    cached.promise = mongoose.connect(MONGODB_URI, opts).then((mongoose) => {
      return mongoose;
    });
  }

  try {
    cached.conn = await cached.promise;
  } catch (e: any) {
    cached.promise = null;
    
    // Provide more helpful error messages
    if (e.code === 8000 || e.message?.includes('authentication failed')) {
      const safeUri = MONGODB_URI.replace(/:[^:@]+@/, ':****@');
      
      // Check if database name is missing
      const hasDatabaseName = /mongodb\+srv:\/\/[^/]+\/[^?]+/.test(MONGODB_URI);
      const databaseWarning = !hasDatabaseName 
        ? '\n⚠️  WARNING: Your connection string is missing the database name!\n   It should end with: /pretriage?retryWrites=true&w=majority\n   Current format: ' + safeUri.split('?')[0] + '/?appName=...\n'
        : '';
      
      const errorMsg = `
MongoDB Authentication Failed!
${databaseWarning}
Common fixes:
1. Check your username and password in the connection string
2. If your password contains special characters (@, #, $, %, &, etc.), you MUST URL-encode them:
   - @ becomes %40
   - # becomes %23
   - $ becomes %24
   - % becomes %25
   - & becomes %26
   - / becomes %2F
   - : becomes %3A
   - ? becomes %3F
   - = becomes %3D

3. Verify your IP is whitelisted in MongoDB Atlas (Network Access)
4. Make sure you're using the correct database user
5. Connection string format should be:
   mongodb+srv://username:password@cluster.mongodb.net/pretriage?retryWrites=true&w=majority

Current connection string (with password hidden): ${safeUri}
      `.trim();
      throw new Error(errorMsg);
    }
    throw e;
  }

  return cached.conn;
}

/**
 * Get the current MongoDB connection status
 * Useful for debugging connection issues
 */
export function getConnectionStatus() {
  const readyStateMap: Record<number, string> = {
    0: 'disconnected',
    1: 'connected',
    2: 'connecting',
    3: 'disconnecting',
  };
  
  return {
    isConnected: mongoose.connection.readyState === 1,
    readyState: mongoose.connection.readyState,
    readyStateText: readyStateMap[mongoose.connection.readyState] || 'unknown',
    hasCachedConnection: !!cached.conn,
    hasPendingPromise: !!cached.promise,
    host: mongoose.connection.host,
    port: mongoose.connection.port,
    name: mongoose.connection.name,
  };
}

export default connectDB;

