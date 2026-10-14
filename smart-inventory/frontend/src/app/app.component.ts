import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { environment } from '../environments/environment';

type Product = { id: number; sku: string; name: string; category: string; reorder_level: number; current_stock: number; status: string };
type Movement = { id: number; warehouse_id: number; warehouse: string; quantity: number; movement_type: 'IN'|'OUT'; note: string|null; created_at: string };

@Component({ selector: 'app-root', standalone: true, imports: [CommonModule, FormsModule], template: `
  <main class="shell">
    <header class="topbar"><div><div class="eyebrow">OPERATIONS</div><h1>Smart Inventory</h1></div><button class="quiet" *ngIf="loggedIn" (click)="logout()">Sign out</button></header>
    <section class="login-card" *ngIf="!loggedIn"><div class="eyebrow">WELCOME BACK</div><h2>Sign in to your workspace</h2><p class="muted">Use your inventory account to continue.</p>
      <form (ngSubmit)="login()"><label>Username<input name="username" [(ngModel)]="username" required autocomplete="username"></label><label>Password<input name="password" type="password" [(ngModel)]="password" required autocomplete="current-password"></label><button class="primary" type="submit" [disabled]="busy">{{busy ? 'Signing in…' : 'Sign in'}}</button></form><p class="error" *ngIf="message">{{message}}</p>
    </section>
    <section *ngIf="loggedIn" class="content"><div class="welcome"><div><div class="eyebrow">INVENTORY OVERVIEW</div><h2>Products</h2><p class="muted">Keep an eye on stock levels across your warehouses.</p></div><button class="quiet" (click)="loadProducts()">Refresh</button></div>
      <div class="toolbar"><input class="search" placeholder="Search SKU, product or category…" [(ngModel)]="search" (ngModelChange)="searchProducts()"><span class="muted">{{total}} products</span><button class="quiet" (click)="loadReorder()">Reorder report</button></div>
      <p class="error" *ngIf="message">{{message}}</p><div class="table-wrap"><table><thead><tr><th>SKU</th><th>Product</th><th>Category</th><th>Current stock</th><th>Status</th></tr></thead><tbody><tr *ngFor="let p of products" (click)="openProduct(p)" class="clickable"><td class="sku">{{p.sku}}</td><td>{{p.name}}</td><td>{{p.category}}</td><td>{{p.current_stock}}</td><td><span class="status" [class.low]="p.status==='LOW'" [class.critical]="p.status==='CRITICAL'">{{p.status}}</span></td></tr><tr *ngIf="!products.length"><td colspan="5" class="empty">No products found.</td></tr></tbody></table></div>
      <div class="pagination"><button class="quiet" [disabled]="page<=1" (click)="changePage(-1)">Previous</button><span class="muted">Page {{page}} of {{pages || 1}}</span><button class="quiet" [disabled]="page>=pages" (click)="changePage(1)">Next</button></div>
    </section>
  </main>
  <div class="overlay" *ngIf="selected" (click)="selected=null"><section class="modal" (click)="$event.stopPropagation()"><button class="close" (click)="selected=null">×</button><div class="eyebrow">{{selected.sku}}</div><h2>{{selected.name}}</h2><p class="muted">{{selected.category}} · Current stock: {{selected.current_stock}}</p><h3>Log a movement</h3><form class="movement-form" (ngSubmit)="saveMovement()"><label>Warehouse<select name="warehouse" [(ngModel)]="movement.warehouse_id" required><option [ngValue]="null" disabled>Select warehouse</option><option *ngFor="let w of warehouses" [ngValue]="w.id">{{w.name}}</option></select></label><div class="form-row"><label>Type<select name="type" [(ngModel)]="movement.movement_type"><option value="IN">Stock in</option><option value="OUT">Stock out</option></select></label><label>Quantity<input name="quantity" type="number" min="1" [(ngModel)]="movement.quantity" required></label></div><label>Note (optional)<input name="note" [(ngModel)]="movement.note" maxlength="500"></label><button class="primary" type="submit" [disabled]="busy">{{busy ? 'Saving…' : 'Save movement'}}</button></form><p class="error" *ngIf="modalMessage">{{modalMessage}}</p><h3>Recent movements</h3><div class="movement-list"><div class="movement" *ngFor="let m of movements"><div><strong>{{m.movement_type==='IN' ? '+' : '−'}}{{m.quantity}}</strong><div class="muted small">{{m.warehouse}} · {{m.note || 'No note'}}</div></div><time>{{m.created_at | date:'medium'}}</time></div><p class="muted" *ngIf="!movements.length">No movements recorded yet.</p></div></section></div>
  ` })
export class AppComponent implements OnInit {
  private http = inject(HttpClient); private api = environment.apiUrl;
  loggedIn = !!sessionStorage.getItem('access_token'); busy = false; username = 'testuser'; password = ''; message = ''; modalMessage = '';
  products: Product[] = []; total = 0; page = 1; pageSize = 10; pages = 1; search = ''; selected: Product | null = null;
  movements: Movement[] = []; warehouses: {id:number;name:string}[] = [];
  movement: {warehouse_id:number|null; movement_type:'IN'|'OUT'; quantity:number; note:string} = {warehouse_id:null,movement_type:'IN',quantity:1,note:''};
  private searchTimer: ReturnType<typeof setTimeout> | undefined;
  ngOnInit() { if (this.loggedIn) this.loadProducts(); }
  login() { this.busy=true; this.message=''; this.http.post<any>(`${this.api}/api/auth/token`,{username:this.username,password:this.password}).subscribe({next:r=>{sessionStorage.setItem('access_token',r.access_token);sessionStorage.setItem('refresh_token',r.refresh_token);this.loggedIn=true;this.busy=false;this.loadProducts();},error:e=>{this.busy=false;this.message=this.errorMessage(e);}}); }
  logout() { sessionStorage.clear();this.loggedIn=false;this.products=[];this.selected=null; }
  loadProducts() { let params=new HttpParams().set('page',this.page).set('page_size',this.pageSize).set('search',this.search);this.http.get<any>(`${this.api}/api/products`,{params}).subscribe({next:r=>{this.products=r.items;this.total=r.total;this.pages=Math.max(1,r.pages);},error:e=>this.message=this.errorMessage(e)}); }
  searchProducts() { if(this.searchTimer) clearTimeout(this.searchTimer);this.searchTimer=setTimeout(()=>{this.page=1;this.loadProducts();},250); }
  changePage(delta:number) { this.page+=delta;this.loadProducts(); }
  openProduct(p:Product) { this.selected=p;this.modalMessage='';this.movement={warehouse_id:null,movement_type:'IN',quantity:1,note:''};this.loadMovements(p.id);this.http.get<any>(`${this.api}/api/products/${p.id}/stock`).subscribe({next:r=>this.warehouses=r.warehouses.map((w:any)=>({id:w.warehouse_id,name:w.warehouse})),error:e=>this.modalMessage=this.errorMessage(e)}); }
  loadMovements(id:number) { this.http.get<any>(`${this.api}/api/products/${id}/movements`).subscribe({next:r=>this.movements=r.items,error:e=>this.modalMessage=this.errorMessage(e)}); }
  saveMovement() { if(!this.selected || !this.movement.warehouse_id || this.movement.quantity<1)return;this.busy=true;this.modalMessage='';this.http.post(`${this.api}/api/movements`,{product_id:this.selected.id,warehouse_id:this.movement.warehouse_id,quantity:Number(this.movement.quantity),movement_type:this.movement.movement_type,note:this.movement.note||null}).subscribe({next:()=>{this.busy=false;this.loadMovements(this.selected!.id);this.loadProducts();this.http.get<any>(`${this.api}/api/products/${this.selected!.id}/stock`).subscribe({next:r=>{this.selected!.current_stock=r.total_stock;},error:()=>{}});this.modalMessage='Movement saved.';},error:e=>{this.busy=false;this.modalMessage=this.errorMessage(e);}}); }
  loadReorder() { this.http.get<any>(`${this.api}/api/reports/reorder`).subscribe({next:r=>{this.products=r.items.map((p:any)=>({...p,status:p.current_stock<=0?'CRITICAL':'LOW'}));this.total=this.products.length;this.pages=1;this.page=1;},error:e=>this.message=this.errorMessage(e)}); }
  private errorMessage(e:HttpErrorResponse) { return e.error?.detail || 'Something went wrong. Please try again.'; }
}
