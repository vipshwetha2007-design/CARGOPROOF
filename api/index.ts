import { handle } from "hono/vercel";
import { app } from "../server/index.js";

export default handle(app);