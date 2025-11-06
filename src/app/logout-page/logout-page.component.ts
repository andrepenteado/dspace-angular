import { Component, Inject } from '@angular/core';
import { APP_CONFIG, AppConfig } from 'src/config/app-config.interface';

@Component({
  selector: 'ds-logout-page',
  styleUrls: ['./logout-page.component.scss'],
  templateUrl: './logout-page.component.html'
})
export class LogoutPageComponent {

    constructor(@Inject(APP_CONFIG) protected appConfig: AppConfig) {}

}
