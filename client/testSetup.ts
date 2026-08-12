import {TextEncoder, TextDecoder} from 'util';
import 'whatwg-fetch';

globalThis.TextEncoder = TextEncoder;
globalThis.TextDecoder = TextDecoder;
